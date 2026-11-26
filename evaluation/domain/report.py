"""Render the public scorecard and reproducible examples from the released receipts."""
import argparse,csv,json
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf8'))
def lines(p):return list(map(json.loads,p.read_text(encoding='utf8').splitlines()))
def percent(r,m):return f"{r[m]}/{r['items']} ({100*r[m]/r['items']:.2f}%)"
def delta(r):
    low,hi=r['ci97_5_pp']
    return f"{r['delta_pp']:+.2f} [{low:+.2f}, {hi:+.2f}]"
def ids(items):return ', '.join(f'`{s}`' for s in items) or 'None'
def verdict(r):return 'Met both criteria' if r['meets_threshold'] else 'Did not meet both criteria'
def row(text,r):return f"| {text} | {percent(r,'base')} | {percent(r,'lora')} | {delta(r)} | {r['improved']} / {r['regressed']} |"
def quote(s):return '\n'.join(('> '+v).rstrip() for v in s.splitlines())

def main():
    p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('domain',type=Path);a=p.parse_args()
    w=a.work;d=a.domain;r=d/'results'
    A=read(r/'business-summary.json');B=read(r/'confirm-b-summary.json');S=read(r/'spider-summary.json');L=read(r/'spider-long-summary.json')
    small={v['id'] for v in lines(r/'spider-long-answers.jsonl')};short=lines(r/'spider-short-answers.jsonl');assert {v['id'] for v in short}==small
    assert len(short)==100
    before={m:sum(v[m+'_pass'] for v in short) for m in ('base','lora')}
    data=lines(r/'business-answers.jsonl');business={v['id']:v for v in data}
    sq={v['id']:v for v in lines(r/'confirm-b-answers.jsonl')}
    sql={s['id']+'-'+str(i):c for s in read(d/'confirm-db.json') for i,c in enumerate(s['cases'],1)}
    execution=read(r/'sql-execution-diagnostic.json')
    ex=execution['models'];both=execution['same_questions_both_executable']
    audit=read(r/'issue-audit.json')
    audited=sum(v.get('model_issue')==v['expected_issue'] for v in audit)
    complete_audit=[v for v in audit if v['arm']=='complete']
    complete_agreement=sum(v['model_issue']==v['expected_issue'] for v in complete_audit)
    by_reviewer=read(r/'reviewer-sensitivity.json')
    first=by_reviewer['reviewer1'];second=by_reviewer['reviewer2']
    title='| Endpoint | Raw Qwen | Final LoRA | Gain in pp [97.5% CI] | Gains / regressions |'
    sep='| --- | ---: | ---: | ---: | ---: |'
    s=['# English checkpoint results','',title,sep,row('A · Business scenario pair',A),row('B · Business SQL',B),row('External · Spider dev',S),'',
       f"Business decisions **{verdict(A).lower()}**. Business SQL **{verdict(B).lower()}**. The registered thresholds were a gain of at least ten percentage points and a positive lower confidence bound. A gain or regression is the same question changing from fail to pass or pass to fail.",'',
       '### Business decisions','',
       '| Arm | Raw Qwen | Final LoRA |','| --- | ---: | ---: |']
    for arm,label in [('missing','Request the necessary input'),('complete','Calculate with all inputs')]:
        s.append(f"| {label} | {A['arm_pass']['base'][arm]}/400 | {A['arm_pass']['lora'][arm]}/400 |")
    s+=['',f"The exploratory classifier agreed with direct masked review on {audited}/{len(audit)} answers, including {complete_agreement}/{len(complete_audit)} complete-input answers. The table below counts classifier flags. Agreement was too low to draw conclusions about the prevalence of either error.",'',
        '| Exploratory error label | Raw Qwen flags | Final LoRA flags |','| --- | ---: | ---: |']
    for arm,issue,label in [('missing','unsupported-number','Unsupported numerical result on a missing-input prompt'),('complete','unnecessary-data-request','Unnecessary request on a complete-input prompt')]:
        if A['issues']:s.append(f"| {label} | {A['issues'].get('base/'+arm+'/'+issue,0)}/400 | {A['issues'].get('lora/'+arm+'/'+issue,0)}/400 |")
    s+=['',f"Blind agreement before adjudication was {A['agree']}/{A['rated']} ({100*A['agree']/A['rated']:.1f}%), Cohen’s κ = {A['kappa']:.2f}. Codex used numeric and request-language screening with direct review of candidate answers. The second AI reviewer was a local Qwen3-4B model. Codex resolved conflicting judgments against the original prompt before the identity key was opened. The answer-level error indicators use separate machine-coded rules and a local AI classifier. They agreed with a direct masked review on {audited}/{len(audit)} hash-selected answers. These rates are exploratory. [Calibration and review](REVIEW.md) · [Diagnostic audit](results/issue-audit.json)",'',
        '| Task family (50 scenarios each) | Raw pairs passed | LoRA pairs passed |','| --- | ---: | ---: |']
    for cat,v in A['categories'].items():s.append(f"| {cat} | {v['base']} | {v['lora']} |")
    s+=['',f"Using only the first reviewer's votes gives {first['base']} raw and {first['lora']} tuned passes out of 400 pairs. Using only the second gives {second['base']} and {second['lora']}. Both fall below the prespecified improvement threshold. Most answers failed under both reviews. [Scores by reviewer](results/reviewer-sensitivity.json)"]
    s+=['','[All scenarios](results/business-scenarios.csv) · [Both answers and verdicts](results/business-answers.jsonl)','',
        '### Business SQL','','| Task family (80 queries each) | Raw Qwen | Final LoRA |','| --- | ---: | ---: |']
    for cat,v in B['categories'].items():s.append(f"| {cat} | {v['base']} | {v['lora']} |")
    s+=['','Individual task families are exploratory. Each database contributed one query per family. The 80 schemas exercise 19 recurring SQL structures. [All answers](results/confirm-b-answers.jsonl) · [All grades](results/confirm-b-grades.csv)','',
        f"Across 480 queries, {ex['base']['executable']} raw answers and {ex['lora']['executable']} tuned answers could execute on all three fixtures. Of {both['items']} questions where both queries executed, raw Qwen returned the right rows on {both['base']} and LoRA on {both['lora']}. This post hoc subset is selected on model output. [Execution diagnostic](results/sql-execution-diagnostic.json)",'',
        f"Raw Qwen reached the 128-token cap on {B['generation']['base']['length']}/480 business SQL answers, compared with {B['generation']['lora']['length']}/480 for the tuned model. A correct extracted statement could still pass if trailing prose was truncated. Shorter, more directly executable output contributes to the gain.",'',
        '### What changes with a longer answer budget?','',
        'The original 128-token run used the entire Spider dev split. A post hoc diagnostic selected 100 of those same questions by a fixed hash, with representation from all 20 databases. Both checkpoints reran the selected prompts at both 128 and 512 output tokens in the same order and batches of four. Decoding settings and the official execution scorer otherwise matched. Every 128-token response was an exact text prefix of the corresponding 512-token response for both models. The scorer also passed a gold-query control on each of the 20 databases.','',
        '| Same 100 Spider questions | Raw Qwen | Final LoRA |','| --- | ---: | ---: |',
        f"| 128 output tokens | {before['base']}/100 | {before['lora']}/100 |",f"| 512 output tokens | {L['base']}/100 | {L['lora']}/100 |",'',
        f"In the full 128-token run, {S['generation']['base'].get('length',0)} raw and {S['generation']['lora'].get('length',0)} tuned answers reached the cap. In the 512-token diagnostic the corresponding counts were {L['generation']['base'].get('length',0)} and {L['generation']['lora'].get('length',0)} of 100. Length-limited answers can still pass when they contain a complete correct query. [Full public benchmark](results/spider-grades.csv) · [Matched 128-token answers](results/spider-short-answers.jsonl) · [512-token answers](results/spider-long-answers.jsonl)",'',
        '### Examples selected by ID','']
    if A['first_gain']:
        k=A['first_gain'];s += [f"**First improved business pair · `{k}`**",'']
        for arm in ('missing','complete'):
            v=business[k+'-'+arm];s += [f"**{arm.title()} prompt**",'',quote(v['prompt']),'','Raw Qwen','',quote(v['base']['answer']),'','Final LoRA','',quote(v['lora']['answer']),'']
    else:s+=['There were no business pairs on which the raw checkpoint failed and the candidate passed.','']
    if B['first_gain']:
        k=B['first_gain'];v=sq[k];s += [f"**First improved business SQL query · `{k}`**",'',quote(sql[k]['question']),'','Raw Qwen','',quote(v['base_answer']),'','Final LoRA','',quote(v['lora_answer']),'']
    s+=['### Regression index','',f"Business pairs ({A['regressed']}): {ids(A['regression_ids'])}",'',f"Business SQL ({B['regressed']}): {ids(B['regression_ids'])}",'',f"Spider dev ({S['regressed']}): {ids(S['regression_ids'])}",'',
        'Only the raw and final checkpoints met the file-identity requirement for this comparison. The intermediate stage has no score on these new sets. [Checkpoint provenance](CHECKPOINTS.md) · [Protocol](PROTOCOL.md) · [Reproduction guide](README.md)']
    (d/'RESULTS.md').write_text('\n'.join(s)+'\n',encoding='utf8')
if __name__=='__main__':main()
