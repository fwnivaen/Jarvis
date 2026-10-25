"""Billing boundaries: no network, credentials or actual model calls."""
import contextlib
import io
import json
import queue
import time
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server
import ultra
import usage_policy
from codex_bridge import CodexBridge, BridgeError

MODEL = 'gpt-6-luna'


def included(percent=10, allowed=True):
    return {'ordinaryUsageAllowed': allowed, 'rateLimits': {'limitId':'codex',
        'primary': {'usedPercent':percent}, 'credits': {'hasCredits':True, 'unlimited':True}}}


class UsagePolicyTests(unittest.TestCase):
    def test_credit_balance_cannot_override_exhausted_or_unknown_allowance(self):
        for snapshot, code in [(included(100),'quota_exhausted'),(included(1,False),'quota_exhausted'),
                (included(0,None),'usage_unavailable'),({},'usage_unavailable'),
                ({'ordinaryUsageAllowed':True,'rateLimits':{}},'usage_unavailable')]:
            with self.subTest(snapshot=snapshot), self.assertRaises(usage_policy.UsagePolicyError) as failure:
                usage_policy.require_included_usage(snapshot)
            self.assertEqual(failure.exception.code,code)
        self.assertEqual(usage_policy.require_included_usage(included())['mode'],'chatgpt-included')

    def test_current_bucket_and_both_windows_are_enforced(self):
        for bucket in ({'primary':{'usedPercent':5},'secondary':{'usedPercent':100}},
                {'primary':{'usedPercent':5},'spendControlReached':True},
                {'primary':{'usedPercent':5},'rateLimitReachedType':'rate_limit_reached'},
                {'primary':{'usedPercent':True}}, {'primary':{'usedPercent':-1}}):
            snapshot=included();snapshot['rateLimitsByLimitId']={'codex':bucket}
            with self.subTest(bucket=bucket), self.assertRaises(usage_policy.UsagePolicyError):
                usage_policy.require_included_usage(snapshot)

    def test_keys_config_and_aliases_cannot_enable_paid_provider(self):
        for backend in ('openai-api','openrouter','unknown'):
            config={'brain':backend,'model':'openai/gpt-6-astra','openai_api_key':'test-only','openrouter_api_key':'test-only'}
            with patch.object(server,'load_config',return_value=config), patch.object(server,'ACTIVE_BRAIN',None), \
                    patch.object(server.urllib.request,'urlopen') as network, patch.object(server.subprocess,'Popen') as process, \
                    contextlib.redirect_stdout(io.StringIO()):
                result=server.ask_brain('test',[],[],'question')
                self.assertTrue(result['error']);self.assertEqual(result['answer'],usage_policy.ERROR_MESSAGES['subscription_required'])
                server.refresh_router_catalog(config)
                self.assertTrue(server.swap_model('openrouter astra')['error'])
                self.assertTrue(all(not c['available'] for c in server.model_catalog()['choices'] if c['backend']=='openrouter'))
                network.assert_not_called();process.assert_not_called()

    def test_cli_forces_chatgpt_and_strips_all_api_keys(self):
        args=server.cli_command('codex',MODEL,'/tmp/empty','/tmp/schema','/tmp/answer')
        for override in usage_policy.CODEX_OVERRIDES:self.assertIn(override,args)
        env=usage_policy.codex_environment(dict.fromkeys(usage_policy.API_ENV_KEYS | usage_policy.ROUTE_ENV_KEYS,'test-only') | {'PATH':'test-path'})
        self.assertEqual(env,{'PATH':'test-path'})

    def test_custom_provider_and_priority_tier_cannot_replace_subscription_route(self):
        config={'forced_login_method':'chatgpt','model_provider':'openai','service_tier':'default'}
        usage_policy.require_codex_config(config)
        for change in ({'forced_login_method':'api'}, {'model_provider':'other'}, {'service_tier':'fast'},
                {'model_providers':{'openai':{'base_url':'https://other.example'}}}):
            with self.subTest(change=change), self.assertRaises(usage_policy.UsagePolicyError):
                usage_policy.require_codex_config(dict(config,**change))

    def test_classic_cli_never_starts_when_usage_check_fails(self):
        for code in usage_policy.ERROR_MESSAGES:
            with patch.object(server,'load_config',return_value={'brain':'codex-cli','model':MODEL}), \
                    patch.object(server,'ACTIVE_BRAIN',None), patch.object(server,'find_codex',return_value='codex'), \
                    patch.object(server.CODEX_USAGE,'require_included_usage',side_effect=BridgeError(code)), \
                    patch.object(server.subprocess,'Popen') as process, contextlib.redirect_stdout(io.StringIO()):
                result=server.ask_brain('test',[],[],'question')
                self.assertEqual(result['answer'],usage_policy.ERROR_MESSAGES[code]);process.assert_not_called()

    def test_app_server_rechecks_login_and_allowance_before_start(self):
        for account, snapshot, code in [({'type':'apiKey'},included(),'subscription_required'),
                ({'type':'chatgpt'},included(100),'quota_exhausted'),
                ({'type':'chatgpt'},included(0,None),'usage_unavailable')]:
            bridge=CodexBridge(None);methods=[]
            def rpc(method,params,deadline):
                methods.append(method)
                if method=='account/read':return {'account':account}
                if method=='account/rateLimits/read':return snapshot
                self.fail('A model thread was started without included usage')
            with patch.object(bridge,'start'), patch.object(bridge,'_rpc',side_effect=rpc):
                with self.assertRaises(BridgeError) as failure:
                    bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                        deadline=time.monotonic()+1,observer=lambda _:None)
                self.assertEqual(failure.exception.code,code)
                self.assertNotIn('thread/start',methods);self.assertNotIn('turn/start',methods)

    def test_cancel_or_expiry_during_allowance_check_cannot_start_model(self):
        for cancelled in (True,False):
            bridge=CodexBridge(None);stop=threading.Event()
            def checked(deadline):
                if cancelled:stop.set()
            with patch.object(bridge,'require_included_usage',side_effect=checked), patch.object(bridge,'_rpc') as rpc:
                with self.assertRaises(BridgeError) as failure:
                    bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                        deadline=time.monotonic()+int(cancelled),observer=lambda _:None,cancel_event=stop)
                self.assertEqual(failure.exception.code,'cancelled' if cancelled else 'timeout');rpc.assert_not_called()

    def test_active_turn_receives_revoked_auth_and_quota_events(self):
        for method,params,code in [('account/updated',{'authMode':'apikey'},'subscription_required'),
                ('account/rateLimits/updated',{'rateLimits':{'primary':{'usedPercent':100}}},'quota_exhausted')]:
            bridge=CodexBridge(None);events=queue.Queue();bridge._calls['test-thread']=events
            bridge._dispatch({'method':method,'params':params},None)
            self.assertEqual(events.get_nowait(),(code,None))
            self.assertEqual(bridge._usage_revoked,code)
            bridge._calls.clear()

    def test_usage_errors_are_nonretryable_for_ultra_and_workflows(self):
        import workflow_runtime
        for code in usage_policy.ERROR_MESSAGES:
            self.assertIn(code,ultra.NO_RETRY)
            self.assertNotIn(code,workflow_runtime.RETRYABLE)
            self.assertIn(code,workflow_runtime.SAFE_FAILURES)

    def test_typed_quota_failure_is_terminal_without_logging_provider_message(self):
        bridge=CodexBridge(None);events=queue.Queue();bridge._calls['test-thread']=events
        bridge._dispatch({'method':'turn/completed','params':{'threadId':'test-thread',
            'turn':{'status':'failed','error':{'codexErrorInfo':'usageLimitExceeded','message':'private sentinel'}}}},None)
        self.assertEqual(events.get_nowait(),('done','quota_exhausted'));bridge._calls.clear()

    def test_revocation_fences_an_already_queued_tool_and_settles_turn(self):
        bridge=CodexBridge(None);bridge._scratch=SimpleNamespace(name='/empty');methods=[]
        bridge._models={MODEL:{'supportedReasoningEfforts':[{'reasoningEffort':'high'}]}}
        def rpc(method,params,deadline):
            methods.append(method)
            if method=='thread/start':return {'thread':{'id':'test-thread'}}
            if method=='turn/start':
                bridge._calls['test-thread'].put(('tool_call',{'id':1,'params':{
                    'tool':'notes_search','turnId':'test-turn','arguments':{'query':'synthetic'}}}))
                bridge._dispatch({'method':'account/rateLimits/updated',
                    'params':{'rateLimits':{'primary':{'usedPercent':100}}}},None)
                return {'turn':{'id':'test-turn'}}
            if method=='turn/interrupt':bridge._calls['test-thread'].put(('done','interrupted'))
            return {}
        try:
            with patch.object(bridge,'require_included_usage'), patch.object(bridge,'_rpc',side_effect=rpc), \
                    patch.object(bridge,'close'), patch.object(bridge,'_send'), patch('builtins.print'), \
                    patch.object(server,'tool_notes_search') as tool:
                with self.assertRaises(BridgeError) as failure:
                    bridge.complete(model=MODEL,effort='high',system='test',payload={},schema={},
                        deadline=time.monotonic()+1,observer=lambda _:None,
                        tools=[{'name':'notes_search'}],tool_handler=tool)
                self.assertEqual(failure.exception.code,'quota_exhausted');tool.assert_not_called()
                self.assertIn('turn/interrupt',methods)
        finally:bridge._scratch=None


if __name__=='__main__':unittest.main()
