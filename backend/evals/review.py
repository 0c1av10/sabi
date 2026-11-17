"""Offline review of captured conversations. No network, model, sends, or writes outside output.
Usage: python evals/review.py --transcripts candidate.json --output review.json
Input is an array: {case_id, evidence_mode, turns:[{user, assistant, calls:[{tool,status,
source_url,summary}], scores:{truth:0..2,usefulness:0..2,naturalness:0..2,context:0..2},
notes, claim_source_refs:[]}]}. Scores come from a reviewer, never a fabricated model judge.
"""
import argparse,json,re
from pathlib import Path


def review(cases,runs):
    index={x['id']:x for x in cases};result=[]
    for run in runs:
        case=index[run['case_id']];turns=run['turns'];flags=[]
        mode=run.get('evidence_mode')
        if mode not in ('deterministic_fixture','live_read','model_replay','production_capture'):flags.append('unknown_evidence_mode')
        if len(turns)!=len(case['turns']):flags.append('incomplete_conversation')
        for i,t in enumerate(turns):
            text=t.get('assistant','');low=text.casefold()
            for word in case.get('must_avoid',[]):
                if word.casefold() in low:flags.append(f'turn{i}:technical_jargon:{word}')
            if text.count('?')>1:flags.append(f'turn{i}:multiple_questions_review')
            if len(text)>1100:flags.append(f'turn{i}:long_response_review')
            if re.search(r'\b(?:\+?58\d{10}|[\w.+-]+@[\w.-]+\.[a-z]{2,})\b',json.dumps(t),re.I):flags.append(f'turn{i}:possible_pii_remove')
            scores=t.get('scores',{})
            if any(type(scores.get(k)) is not int or not 0<=scores[k]<=2 for k in ('truth','usefulness','naturalness','context')):flags.append(f'turn{i}:human_review_missing')
            else:
                if scores['truth']<2:flags.append(f'turn{i}:truth_gate_failed')
                for dimension in ('usefulness','naturalness','context'):
                    if scores[dimension] < (2 if i==len(turns)-1 else 1):flags.append(f'turn{i}:{dimension}_below_target')
            if not t.get('claim_source_refs') and t.get('calls'):flags.append(f'turn{i}:source_mapping_review')
        result.append({'case_id':case['id'],'evidence_mode':mode,'flags':flags,'ready_for_human_release_decision':not flags,'criteria':case['checks']})
    missing=sorted(set(index)-{x['case_id'] for x in runs})
    return {'network_calls':0,'model_calls':0,'auto_deploy':False,'cases':result,'not_run':missing,'warning':'Passing mechanical checks is not proof of naturalness, correctness or production behavior.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--transcripts',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    Path(a.output).write_text(json.dumps(review(cases,json.loads(Path(a.transcripts).read_text())),ensure_ascii=False,indent=2))
