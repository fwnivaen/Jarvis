"""Isolated official Deep Agents SDK integration. No host tools or permanent memory."""
import json
import os
from pathlib import Path
import sys
import threading
import time

# -I prevents ambient PYTHONPATH/package injection. Only reviewed repo modules.
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from helper_protocol import frame,parse,MAX_FRAME_BYTES

PROCEDURE=json.loads((Path(__file__).resolve().parent/'procedure.json').read_text())

MAX_MODEL_CALLS=8
MAX_TOOL_CALLS=16
MAX_DELEGATIONS=1
MAX_OUTPUT_TOKENS=1024
MAX_REPORTED_TOKENS=12000
MAX_CONTEXT_CHARS=48000
MAX_SCRATCH_BYTES=16000
MAX_SCRATCH_FILES=4
RECURSION_LIMIT=24
SAFE_NAMES=frozenset({'notes_search','note_read','preferences_get','scratch_put','scratch_get','write_todos','task'})
EXCLUDED=frozenset({'execute','ls','read_file','write_file','edit_file','glob','grep','delete_file'})
KEY=os.environ.pop('JARVIS_HELPER_TOKEN')
IN_SEQ=OUT_SEQ=0
RPC_LOCK=threading.RLock()


def send(kind,data):
    global OUT_SEQ
    OUT_SEQ+=1
    sys.stdout.write(frame(KEY,OUT_SEQ,kind,data));sys.stdout.flush()


def receive():
    global IN_SEQ
    IN_SEQ+=1
    return parse(KEY,IN_SEQ,sys.stdin.readline(MAX_FRAME_BYTES+1))


def rpc(name,arguments,worker=False):
    with RPC_LOCK:
        send('tool',{'name':name,'arguments':arguments,'worker':worker})
        response=receive()
        if response['kind']!='tool_result':raise ValueError('Invalid gateway result')
        return response['data']['result']


def build(model,budget,child=False):
    from deepagents import create_deep_agent
    from deepagents.backends import StateBackend
    from deepagents.profiles import HarnessProfile,GeneralPurposeSubagentProfile,register_harness_profile
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.tools import tool

    # Tool exclusion is UI hygiene; middleware and non-sandbox backend enforce.
    for provider in ('openai','jarvis-fixture','fixture'):
        register_harness_profile(provider,HarnessProfile(excluded_tools=EXCLUDED,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)))

    class BudgetMiddleware(AgentMiddleware):
        def before_model(self,state,runtime):
            with budget['lock']:
                budget['models']+=1
                if (budget['models']>MAX_MODEL_CALLS or time.monotonic()>=budget['deadline']
                        or sum(len(str(m.content)) for m in state['messages'])>MAX_CONTEXT_CHARS):
                    raise ValueError('Model budget exceeded')
                send('step',{})
        def after_model(self,state,runtime):
            usage=getattr(state['messages'][-1],'usage_metadata',None)
            if usage is None:raise ValueError('Usage accounting unavailable')
            with budget['lock']:
                budget['tokens']+=usage['total_tokens']
                send('usage',{'total_tokens':usage['total_tokens']})
                if budget['tokens']>MAX_REPORTED_TOKENS:raise ValueError('Token budget exceeded')
        def wrap_tool_call(self,request,handler):
            name=request.tool_call['name']
            with budget['lock']:
                budget['tools']+=1
                if name not in SAFE_NAMES or budget['tools']>MAX_TOOL_CALLS or time.monotonic()>=budget['deadline']:
                    raise ValueError('Tool scope or budget exceeded')
                if name=='task':
                    budget['delegations']+=1
                    if child or budget['delegations']>MAX_DELEGATIONS:raise ValueError('Delegation scope exceeded')
            return handler(request)

    @tool
    def notes_search(query:str)->dict:
        """Search approved task notes through the JARVIS gateway."""
        return rpc('notes_search',{'query':query},child)
    @tool
    def note_read(id:int)->dict:
        """Read approved task note and its source revision."""
        return rpc('note_read',{'id':id},child)
    @tool
    def preferences_get()->dict:
        """Read explicit approved preferences through the JARVIS gateway."""
        return rpc('preferences_get',{},child)
    @tool
    def scratch_put(name:str,text:str)->dict:
        """Write bounded virtual scratch; never a host path or permanent memory."""
        if not name.isidentifier() or len(name)>64:raise ValueError('Invalid scratch name')
        candidate=dict(budget['scratch'],**{name:text})
        if len(candidate)>MAX_SCRATCH_FILES or sum(len(x.encode()) for x in candidate.values())>MAX_SCRATCH_BYTES:
            raise ValueError('Scratch quota exceeded')
        budget['scratch']=candidate
        return {'saved':True}
    @tool
    def scratch_get(name:str)->str:
        """Read virtual scratch scoped to this run."""
        return budget['scratch'][name]

    # The native backend holds only ephemeral graph state and is never a sandbox.
    # No filesystem tools can execute: excluded AND rejected in wrap_tool_call.
    backend=StateBackend()
    tools=[notes_search,note_read,preferences_get,scratch_put,scratch_get]
    subagents=[] if child else [{'name':'Scout','description':'One bounded evidence check.',
        'runnable':build(model,budget,child=True)}]
    return create_deep_agent(model=model,tools=tools,backend=backend,
        middleware=[BudgetMiddleware()],subagents=subagents,memory=None,skills=None,store=None,
        response_format=None,debug=False,name='jarvis-worker' if child else 'jarvis-research',
        system_prompt=PROCEDURE['instructions'])


def fixture_model(scenario):
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage,ToolMessage
    from langchain_core.outputs import ChatGeneration,ChatResult
    class Fixture(BaseChatModel):
        @property
        def _llm_type(self):return 'jarvis-fixture'
        def bind_tools(self,tools,**kwargs):return self
        def _generate(self,messages,stop=None,run_manager=None,**kwargs):
            if scenario=='slow':time.sleep(30)
            tool_messages=[m for m in messages if isinstance(m,ToolMessage)]
            n=len(tool_messages)
            choices=[('notes_search',{'query':'synthetic'}),('note_read',{'id':1}),
                ('scratch_put',{'name':'finding','text':'synthetic evidence'}),('scratch_get',{'name':'finding'})]
            if scenario=='forbidden':choices=[('execute',{'command':'echo forbidden'})]
            if scenario=='delegation':
                # Child sees its own assignment and can never delegate again.
                is_child=any(getattr(m,'type',None)=='human' and m.content=='bounded child check' for m in messages)
                choices=[('note_read',{'id':1})] if is_child else [('task',{'description':'bounded child check','subagent_type':'Scout'})]
            if n<len(choices):
                name,args=choices[n]
                msg=AIMessage(content='',tool_calls=[{'name':name,'args':args,'id':'fixture-'+str(n),'type':'tool_call'}])
            else:
                value={'answer':'The synthetic budget is 100 dollars.','nodes':[1],'about_notes':True,
                    'evidence':[{'node':1,'quote':'The synthetic budget is 100 dollars.'}],'calculations':[]}
                msg=AIMessage(content=json.dumps(value))
            msg.usage_metadata={'input_tokens':10,'output_tokens':5,'total_tokens':15}
            return ChatResult(generations=[ChatGeneration(message=msg)])
    return Fixture()


def main():
    initial=receive()
    if initial['kind']!='start':raise ValueError('Start required')
    config=initial['data']
    from langsmith import tracing_context
    if config['fixture']:model=fixture_model(config['scenario'])
    else:
        from langchain_openai import ChatOpenAI
        model=ChatOpenAI(model=config['model'],api_key=os.environ.pop('JARVIS_DEEPAGENTS_API_KEY'),
            max_tokens=MAX_OUTPUT_TOKENS,max_retries=0,timeout=config['duration_s'])
    budget={'lock':threading.RLock(),'deadline':time.monotonic()+config['duration_s'],
        'models':0,'tokens':0,'tools':0,'delegations':0,'scratch':{}}
    with tracing_context(enabled=False):
        graph=build(model,budget)
        send('started',{})
        output=graph.invoke({'messages':[{'role':'user','content':config['question']}]},
            {'recursion_limit':RECURSION_LIMIT,'max_concurrency':1,'callbacks':[]})
        send('result',json.loads(output['messages'][-1].content))


if __name__=='__main__':
    try:main()
    except Exception:send('error',{'code':'sdk_failure'})
