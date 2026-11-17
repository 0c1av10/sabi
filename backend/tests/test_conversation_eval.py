import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('eval_review',Path(__file__).parents[1]/'evals/review.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

def test_review_does_not_pass_unevaluated_or_technical_answer():
    cases=[{'id':'plaza','turns':['a'],'checks':['truth'],'must_avoid':['MCP']}]
    report=mod.review(cases,[{'case_id':'plaza','evidence_mode':'deterministic_fixture','turns':[{'assistant':'MCP no funciona'}]}])
    assert report['network_calls']==0 and report['model_calls']==0 and not report['auto_deploy']
    assert not report['cases'][0]['ready_for_human_release_decision']
    assert any('technical_jargon' in x for x in report['cases'][0]['flags'])
    assert any('human_review_missing' in x for x in report['cases'][0]['flags'])
