"""
gerar_data.py — PipeLovers Reimplantação
Atualiza os dados embutidos no index.html.

USO:
    python gerar_data.py

Requer na mesma pasta:
    members-report.csv / usuarios.csv / clientes.csv
    consumo.csv      ← relatório de consumo (aulas assistidas)
    index.html
"""
import pandas as pd, re, json
from pathlib import Path

BASE = Path(__file__).parent
GENERIC = {'Aplicativo','Full Pass','Pré-vendas','Gestão','Executivos','Canais','Class',
           'Novo grupo - Priscila','Forma Turismo','Pré Vendas'}

# ── HELPER: lê CSV detectando separador automaticamente ─────
def read_csv_auto(path):
    """Tenta ',' e ';' — retorna o que tiver mais colunas."""
    try:
        df_c = pd.read_csv(path, sep=',', on_bad_lines='skip', engine='python')
    except Exception:
        df_c = pd.DataFrame()
    try:
        df_s = pd.read_csv(path, sep=';', on_bad_lines='skip', engine='python')
    except Exception:
        df_s = pd.DataFrame()
    return df_s if df_s.shape[1] > df_c.shape[1] else df_c

members  = read_csv_auto(BASE/'members-report.csv')
usuarios = read_csv_auto(BASE/'usuarios.csv')
clientes = read_csv_auto(BASE/'clientes.csv')
report   = read_csv_auto(BASE/'consumo.csv')

members['email_lower']  = members['Email'].str.lower().str.strip()
usuarios['email_lower'] = usuarios['Url do E-mail do Membro'].str.lower().str.strip()
report['email_lower']   = report['Email'].str.lower().str.strip()
usu_dedup = usuarios[['email_lower','Nome da Empresa']].drop_duplicates('email_lower')

# ── CSM por empresa ─────────────────────────────────────────
company_csm = {}
for _, r in clientes[['Empresa','CSM']].dropna(subset=['Empresa']).iterrows():
    company_csm[r['Empresa'].strip().lower()] = r['CSM']

def get_csm(name):
    if pd.isna(name) or str(name).strip()=='': return ''
    nl = str(name).strip().lower()
    if nl in company_csm: return str(company_csm[nl])
    for k,v in company_csm.items():
        if nl in k or k in nl: return str(v)
    return ''

# ── STATUS do cliente (Ativo / Inativo / Churn / Try and Buy) ─
#    Quando a mesma empresa tem múltiplos contratos com status diferentes,
#    priorizamos o mais "vivo" (Ativo > Try and Buy > Inativo > Churn).
_PRIORITY = {'Ativo':0, 'Try and Buy':1, 'Inativo':2, 'Churn':3}
_cli = clientes.dropna(subset=['Empresa']).copy()
_cli['_emp'] = _cli['Empresa'].str.strip().str.lower()
_cli['_pri'] = _cli['Status'].map(_PRIORITY).fillna(99)
_cli = _cli.sort_values('_pri').drop_duplicates('_emp')
company_status = dict(zip(_cli['_emp'], _cli['Status']))

def get_status(name):
    """Retorna o Status (Ativo/Inativo/Churn/Try and Buy) da empresa, ou '' se não mapeada."""
    if pd.isna(name) or str(name).strip()=='': return ''
    nl = str(name).strip().lower()
    if nl in company_status: return str(company_status[nl])
    for k,v in company_status.items():
        if nl in k or k in nl: return str(v)
    return ''

def is_churn(name):
    return get_status(name) == 'Churn'

# ── EXTRATOR DE EMPRESA A PARTIR DA TURMA ───────────────────
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

def turma_to_company(turma):
    lst = extract_companies(turma)
    return lst[0] if lst else None

def detect_internal(email):
    if pd.isna(email): return False
    return str(email).split('@')[-1].lower() in ('pipelovers.net','curseduca.com')

def empresa_from_domain(email):
    if pd.isna(email): return ''
    d = str(email).lower()
    if 'sidrasul' in d: return 'Sidrasul Sistemas Hidráulicos Ltda'
    if 'bmchyundai' in d: return 'BMC Hyundai'
    if 'cartrom' in d: return 'CARTROM'
    if 'medika' in d: return 'Medika'
    if 'tecnogera' in d: return 'Tecnogera'
    if 'becomex' in d: return 'Becomex'
    if 'progic' in d: return 'Progic'
    if 'premier' in d: return 'Grupo Premier Alimentos'
    return ''

def clean(v):
    if pd.isna(v): return ''
    return str(v).replace('"','&quot;')

# ── REIMPLANTAÇÃO ───────────────────────────────────────────
members['empresas_lista'] = members['Turmas'].apply(extract_companies)
members['reimplantado']   = members['empresas_lista'].apply(lambda x: len(x)>0)
members['empresa_turma']  = members['empresas_lista'].apply(lambda x: x[0] if x else None)
members['acessou']        = members['Último acesso'] != 'Nunca acessou'
members = members.merge(usu_dedup, on='email_lower', how='left')
members['empresa_final']  = members['empresa_turma'].combine_first(members['Nome da Empresa'])
members['CSM']            = members['empresa_turma'].apply(get_csm)
mask = members['CSM']==''
members.loc[mask,'CSM']   = members.loc[mask,'empresa_final'].apply(get_csm)

# ── FILTRO CHURN ────────────────────────────────────────────
#    Usuários cuja empresa está em status "Churn" não pertencem mais
#    à PipeLovers e precisam ser removidos de todas as contagens.
members['status_cliente'] = members['empresa_final'].apply(get_status)
members['eh_churn']       = members['status_cliente'] == 'Churn'
_total_churn_removidos    = int(members['eh_churn'].sum())
members_validos = members[~members['eh_churn']].copy()

reimpl    = members_validos[ members_validos['reimplantado']].copy()
nao_reimpl= members_validos[~members_validos['reimplantado']].copy()
nao_enc   = members_validos[~members_validos['email_lower'].isin(usu_dedup['email_lower'])].copy()

empresas_reimpl = sorted(set(e for lst in reimpl['empresas_lista'] for e in lst))
total_r = len(reimpl); acessaram = int(reimpl['acessou'].sum())

def to_rows(df):
    rows=[]
    for _,r in df.iterrows():
        emp=clean(r.get('empresa_turma','') or r.get('empresa_final','') or r.get('Nome da Empresa',''))
        rows.append({'nome':clean(r.get('Nome','')),'email':clean(r.get('Email','')),
                     'empresa':emp,'csm':clean(r.get('CSM','')),'ultimo_acesso':clean(r.get('Último acesso','')),
                     'situacao':clean(r.get('Situação','')),'turmas':clean(r.get('Turmas','')),
                     'data_criacao':clean(r.get('Data de criação',''))})
    return rows

por_empresa=[]
for emp in empresas_reimpl:
    df_e=reimpl[reimpl['empresas_lista'].apply(lambda x:emp in x)]
    acc=int(df_e['acessou'].sum()); tot=len(df_e)
    csm_mode=df_e['CSM'].mode()
    por_empresa.append({'empresa':emp,'csm':csm_mode.iloc[0] if len(csm_mode) else '',
                        'total':tot,'acessaram':acc,'nao_acessaram':tot-acc,'pct':round(acc/tot*100,1) if tot else 0})

csm_list=sorted(set(list(reimpl['CSM'].unique())+list(nao_reimpl['CSM'].unique()))-{''})
por_csm=[]
for csm in csm_list:
    r=reimpl[reimpl['CSM']==csm]; nr=nao_reimpl[nao_reimpl['CSM']==csm]
    acc=int(r['acessou'].sum()); tot=len(r)
    emps=set(e for lst in r['empresas_lista'] for e in lst)
    por_csm.append({'csm':csm,'empresas':len(emps),'total':tot,'acessaram':acc,
                    'nao_acessaram':tot-acc,'pct':round(acc/tot*100,1) if tot else 0,'pendentes':len(nr)})

# ── AULAS ───────────────────────────────────────────────────
rp = report.merge(usu_dedup, on='email_lower', how='left')
rp['empresa_turma'] = rp['Turmas'].apply(turma_to_company)
rp['is_internal']   = rp['email_lower'].apply(detect_internal)
rp['empresa_final'] = rp.apply(lambda row:
    clean(row['empresa_turma']) or clean(row.get('Nome da Empresa','')) or
    empresa_from_domain(row['email_lower']) or
    ('PipeLovers' if row['is_internal'] else ''), axis=1)
rp['empresa_final'] = rp['empresa_final'].str.replace(r'^[Cc]artrom$','CARTROM',regex=True)
rp['CSM'] = rp['empresa_final'].apply(get_csm)
rp.loc[(rp['CSM']=='') & rp['is_internal'],'CSM'] = 'Gunther Weissbock'

# NOTA: aulas NÃO são filtradas por Churn — consumo histórico permanece mesmo
# quando a empresa saiu depois. Assim evitamos distorcer tendências de consumo.

rp['data_compra_dt'] = pd.to_datetime(rp['Data da compra'], format='%d/%m/%Y', errors='coerce')
rp['mes'] = rp['data_compra_dt'].dt.strftime('%Y-%m').fillna('')

rows_aulas=[]
for _,row in rp.iterrows():
    rows_aulas.append({'nome':clean(row['Nome']),'email':clean(row['Email']),
                       'empresa':clean(row['empresa_final']),'csm':clean(row['CSM']),
                       'conteudo':clean(row['Conteúdo']),'turma':clean(row['Turmas']),
                       'progresso':clean(row['Progresso']),'matricula':clean(row['Matrícula']),
                       'data_compra':clean(row['Data da compra']),'mes':row['mes'],
                       'situacao':clean(row['Situação do membro'])})

por_empresa_aulas=[]
for emp,df_e in rp[rp['empresa_final']!=''].groupby('empresa_final'):
    csm_mode=df_e['CSM'].mode()
    por_empresa_aulas.append({'empresa':str(emp),'csm':csm_mode.iloc[0] if len(csm_mode) else '',
                              'total_aulas':len(df_e),'usuarios':df_e['email_lower'].nunique(),'conteudos':df_e['Conteúdo'].nunique()})
por_empresa_aulas.sort(key=lambda x:-x['total_aulas'])

top_conteudos=sorted([{'conteudo':str(c),'total':len(df_c)} for c,df_c in rp.groupby('Conteúdo')],key=lambda x:-x['total'])
meses_aulas=sorted([m for m in rp['mes'].dropna().unique() if m])
summary_aulas={'total_aulas':len(rp),'unique_users':rp['email_lower'].nunique(),
               'unique_empresas':rp[rp['empresa_final']!='']['empresa_final'].nunique(),'unique_conteudos':rp['Conteúdo'].nunique()}

# ── INJETA NO HTML ───────────────────────────────────────────
now=pd.Timestamp.now().strftime('%d/%m/%Y')
js =(f'var UPD={json.dumps(now)};\n'
     +'var SUMMARY='+json.dumps({'empresas_reimplantadas':len(empresas_reimpl),'total_usuarios_reimpl':total_r,
                                 'acessaram':acessaram,'nao_acessaram':total_r-acessaram,'pct_adocao':round(acessaram/total_r*100,1) if total_r else 0,
                                 'nao_encontrados':len(nao_enc),'nao_reimplantados':len(nao_reimpl),'gerado_em':now})+';\n'
     +'var POR_EMPRESA='+json.dumps(por_empresa,ensure_ascii=False)+';\n'
     +'var POR_CSM='+json.dumps(por_csm,ensure_ascii=False)+';\n'
     +'var ACESSARAM='+json.dumps(to_rows(reimpl[reimpl['acessou']]),ensure_ascii=False)+';\n'
     +'var NAO_ACESSARAM='+json.dumps(to_rows(reimpl[~reimpl['acessou']]),ensure_ascii=False)+';\n'
     +'var NAO_REIMPL='+json.dumps(to_rows(nao_reimpl),ensure_ascii=False)+';\n'
     +'var NAO_ENC='+json.dumps(to_rows(nao_enc),ensure_ascii=False)+';\n'
     +'var SUMMARY_AULAS='+json.dumps(summary_aulas,ensure_ascii=False)+';\n'
     +'var ROWS_AULAS='+json.dumps(rows_aulas,ensure_ascii=False)+';\n'
     +'var POR_EMPRESA_AULAS='+json.dumps(por_empresa_aulas,ensure_ascii=False)+';\n'
     +'var TOP_CONTEUDOS='+json.dumps(top_conteudos,ensure_ascii=False)+';\n'
     +'var MESES_AULAS='+json.dumps(meses_aulas,ensure_ascii=False)+';\n')

html=(BASE/'index.html').read_text(encoding='utf-8')
marker='/* ══ DATA ══════════════════════════════════════════════════════ */'
end_marker='/* ══ HELPERS'
start=html.index(marker)+len(marker)
end=html.index(end_marker)
html=html[:start]+'\n'+js+html[end:]
(BASE/'index.html').write_text(html,encoding='utf-8')

print(f'✅ index.html atualizado — {now}')
print(f'   Empresas reimplantadas      : {len(empresas_reimpl)} | Usuários: {total_r} | Acessaram: {acessaram}')
print(f'   Aulas registradas           : {len(rp)} | Usuários únicos: {rp["email_lower"].nunique()} | Conteúdos: {rp["Conteúdo"].nunique()}')
print(f'   ⚠ Removidos (empresas Churn): {_total_churn_removidos} membros (aulas mantidas no histórico)')
