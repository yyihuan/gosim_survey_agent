#!/usr/bin/env python3
"""仅本地AST分析；源码全量scope，不启用模型后端。"""
import hashlib,json,subprocess,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
settings=json.loads((ROOT/'experiments/current/environment.json').read_text())
EXCLUDE=['*.md','*.toml','*.json','*.env*','*.txt','Dockerfile','*.sh','*.command','*.csv','*.pyc']
records=[]
for name,source in [('python-graph',settings['agent']),('backend-graph',settings['runner'])]:
    output=ROOT/'experiments/current/rules-audit'/name
    args=['graphify','extract',str(ROOT/source),'--out',str(output),'--scope','all']
    for pattern in EXCLUDE:args+=['--exclude',pattern]
    # graphify即使指定out也向输入目录写AST缓存，故只分析临时副本。
    with tempfile.TemporaryDirectory(prefix='survey-ast-') as staged:
        for source_file in (ROOT/source).rglob('*.py'):
            if '__pycache__' in source_file.parts:continue
            target=Path(staged)/source_file.relative_to(ROOT/source)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source_file,target)
        staged_args=args.copy();staged_args[2]=staged
        subprocess.run(staged_args,check=True)
    graph=output/'.graphify/graph.json';data=json.loads(graph.read_text())
    files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/source).rglob('*.py')) if '__pycache__' not in p.parts}
    records.append({'name':name,'source':source,'command':args,'scope':'all','staged_input':True,'semantic_backend':None,'files':files,
        'nodes':len(data['nodes']),'edges':len(data['links']),'graph_sha256':hashlib.sha256(graph.read_bytes()).hexdigest()})
(ROOT/'experiments/current/rules-audit/source-graphs.json').write_text(json.dumps({'schema':'local-ast-graphs-v1','graphs':records},ensure_ascii=False,indent=2)+'\n')
