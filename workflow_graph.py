"""LangGraph owns scheduling, parallel fan-out, joining and checkpoint recovery."""
import operator
from typing import Annotated, TypedDict

GRAPH_RECURSION_LIMIT = 12


class WorkflowState(TypedDict, total=False):
    question: str
    workflow: str
    notes: list
    tasks: list
    reports: Annotated[dict, operator.or_]
    result: dict


def compile_workflow(jobs, saver):
    # Optional dependency: importing the ordinary server still needs only stdlib.
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Send
    graph = StateGraph(WorkflowState)
    graph.add_node('retrieve', jobs.retrieve)
    graph.add_node('assign', jobs.assign)
    graph.add_node('worker', jobs.worker)
    graph.add_node('review', jobs.review)
    graph.add_edge(START, 'retrieve')
    graph.add_edge('retrieve', 'assign')
    graph.add_conditional_edges('assign', lambda state: [Send('worker', {
        'question': state['question'], 'notes': state['notes'], 'task': task,
        'index': index}) for index, task in enumerate(state['tasks'])], ['worker'])
    graph.add_edge('worker', 'review')
    graph.add_edge('review', END)
    return graph.compile(checkpointer=saver)
