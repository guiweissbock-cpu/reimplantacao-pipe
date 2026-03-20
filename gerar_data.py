"""
gerar_data.py — PipeLovers Reimplantação
Substitui os dados embutidos no index.html.

USO:
    python gerar_data.py

Requer na mesma pasta:
    members-report.csv  /  usuarios.csv  /  clientes.csv  /  index.html

Gera:
    index.html  (atualizado com os novos dados)
"""
import pandas as pd, re, json
from pathlib import Path

BASE = Path(__file__).parent
GENERIC = {'Aplicativo','Full Pass','Pré-vendas','Gestão','Executivos','Canais','Class',
           'Novo grupo - Priscila','Forma Turismo'}

members  = pd.read_csv(BASE/'members-report.csv')
usuarios = pd.read_csv(BASE/'usuarios.csv')
clientes = pd.read_csv(BASE/'clientes.csv')

members['email_lower']  = members['Email'].str.lower().str.strip()
usuarios['email_lower'] = usuarios['Url do E-mail do Membro'].str.lower().str.strip()

def extract_companies(turma):
    if pd.isna(turma): return []
    companies = []
    for p in [x.strip() for x in str(turma).split(',')]:
        m1 = re.match(r'^\d+ - \d+ - (.+)$', p)
        if m1: companies.append(m1.group(1).strip()); continue
        m2 = re.match(r'^\d+ - (.+)$', p)
        if m2:
            name = m2.group(1).strip()
            if name not in GENERIC: companies.append(name)
    return companies

members['empresas_lista'] = members['Turmas'].apply(extract_companies)
members['reimplantado']   = members['empresas_lista'].apply(lambda x: len(x)>0)
members['empresa_turma']  = members['empresas_lista'].apply(lambda x: x[0] if x else None)
members['acessou']        = members['Último acesso'] != 'Nunca acessou'

usu_dedup = usuarios[['email_lower','Nome da Empresa']].drop_duplicates('email_lower')
members = members.merge(usu_dedup, on='email_lower', how='left')
members['empresa_final'] = members['empresa_turma'].combine_first(members['Nome da Empresa'])

company_csm = {}
for _, r in clientes[['Empresa','CSM']].dropna(subset=['Empresa']).iterrows():
    company_csm[r['Empresa'].strip().lower()] = r['CSM']

def get_csm(name):
    if pd.isna(name): return ''
    nl = str(name).strip().lower()
    if nl in company_csm: return str(company_csm[nl])
    for k,v in company_csm.items():
        if nl in k or k in nl: return str(v)
    return ''

members['CSM'] = members['empresa_turma'].apply(get_csm)
mask = members['CSM']==''
members.loc[mask,'CSM'] = members.loc[mask,'empresa_final'].apply(get_csm)

reimpl    = members[members['reimplantado']].copy()
nao_reimpl= members[~members['reimplantado']].copy()
nao_enc   = members[~members['email_lower'].isin(usu_dedup['email_lower'])].copy()
empresas_reimpl = sorted(set(e for lst in reimpl['empresas_lista'] for e in lst))

def clean(v):
    if pd.isna(v): return ''
    return str(v).replace('"','&quot;')

por_empresa = []
for emp in empresas_reimpl:
    df_e = reimpl[reimpl['empresas_lista'].apply(lambda x: emp in x)]
    acc = int(df_e['acessou'].sum()); tot = len(df_e)
    csm_mode = df_e['CSM'].mode()
    por_empresa.append({'empresa':emp,'csm':csm_mode.iloc[0] if len(csm_mode) else '',
        'total':tot,'acessaram':acc,'nao_acessaram':tot-acc,'pct':round(acc/tot*100,1) if tot else 0})

csm_list = sorted(set(list(reimpl['CSM'].unique())+list(nao_reimpl['CSM'].unique()))-{''})
por_csm = []
for csm in csm_list:
    r=reimpl[reimpl['CSM']==csm]; nr=nao_reimpl[nao_reimpl['CSM']==csm]
    acc=int(r['acessou'].sum()); tot=len(r)
    emps=set(e for lst in r['empresas_lista'] for e in lst)
    por_csm.append({'csm':csm,'empresas':len(emps),'total':tot,'acessaram':acc,
        'nao_acessaram':tot-acc,'pct':round(acc/tot*100,1) if tot else 0,'pendentes':len(nr)})

def to_rows(df):
    rows=[]
    for _,r in df.iterrows():
        emp=clean(r.get('empresa_turma','') or r.get('empresa_final','') or r.get('Nome da Empresa',''))
        rows.append({'nome':clean(r.get('Nome','')),'email':clean(r.get('Email','')),
            'empresa':emp,'csm':clean(r.get('CSM','')),'ultimo_acesso':clean(r.get('Último acesso','')),
            'situacao':clean(r.get('Situação','')),'turmas':clean(r.get('Turmas','')),'data_criacao':clean(r.get('Data de criação',''))})
    return rows

total_r=len(reimpl); acessaram=int(reimpl['acessou'].sum())

# Build JS block
js = 'var UPD=' + json.dumps(pd.Timestamp.now().strftime('%d/%m/%Y')) + ';\n'
js += 'var SUMMARY=' + json.dumps({'empresas_reimplantadas':len(empresas_reimpl),'total_usuarios_reimpl':total_r,'acessaram':acessaram,'nao_acessaram':total_r-acessaram,'pct_adocao':round(acessaram/total_r*100,1) if total_r else 0,'nao_encontrados':len(nao_enc),'nao_reimplantados':len(nao_reimpl),'gerado_em':pd.Timestamp.now().strftime('%d/%m/%Y')}) + ';\n'
js += 'var POR_EMPRESA=' + json.dumps(por_empresa, ensure_ascii=False) + ';\n'
js += 'var POR_CSM=' + json.dumps(por_csm, ensure_ascii=False) + ';\n'
js += 'var ACESSARAM=' + json.dumps(to_rows(reimpl[reimpl['acessou']]), ensure_ascii=False) + ';\n'
js += 'var NAO_ACESSARAM=' + json.dumps(to_rows(reimpl[~reimpl['acessou']]), ensure_ascii=False) + ';\n'
js += 'var NAO_REIMPL=' + json.dumps(to_rows(nao_reimpl), ensure_ascii=False) + ';\n'
js += 'var NAO_ENC=' + json.dumps(to_rows(nao_enc), ensure_ascii=False) + ';\n'

# Replace data block in index.html
html = (BASE/'index.html').read_text(encoding='utf-8')
marker = '/* ══ DATA ══════════════════════════════════════════════════════ */'
end_marker = '/* ══ HELPERS'
start = html.index(marker) + len(marker)
end   = html.index(end_marker)
html = html[:start] + '\n' + js + html[end:]
(BASE/'index.html').write_text(html, encoding='utf-8')

print(f'✅ index.html atualizado — {pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")}')
print(f'   Empresas: {len(empresas_reimpl)} | Reimplantados: {total_r} | Acessaram: {acessaram} ({round(acessaram/total_r*100,1) if total_r else 0}%)')
print(f'   Não reimplantados: {len(nao_reimpl)} | Não encontrados: {len(nao_enc)}')
