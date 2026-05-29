"""
gerar_data.py — PipeLovers Reimplantação
Atualiza os dados embutidos no index.html.

USO:
    python gerar_data.py

Requer na mesma pasta:
    grupos_acesso.csv   ← fonte da verdade de empresas/grupos (join por código)
    members-report.csv  ← export da plataforma com membros
    clientes.csv        ← base de clientes com CSM responsável
    consumo.csv         ← relatório de consumo (aulas assistidas)
    index.html
"""

import pandas as pd, re, json
from pathlib import Path

BASE = Path(__file__).parent

# ── CONFIGURAÇÃO ─────────────────────────────────────────────
# Trilhas internas a excluir (IDs dos grupos)
TRILHAS_INTERNAS = {12, 13, 14, 15, 16, 17, 222, 23}

# True  → inclui empresas churn/inativo que têm logins (são reimplantadas de facto)
# False → filtra fora empresas com status Churn/Inativo
INCLUIR_CHURN_REIMPLANTADAS = True

# ── HELPERS ──────────────────────────────────────────────────
def detect_sep(path):
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        first = f.read(4096)
    return ';' if first.count(';') > first.count(',') else ','

def read_csv(path):
    sep = detect_sep(path)
    return pd.read_csv(path, sep=sep, engine='python', encoding='utf-8-sig', on_bad_lines='skip')

def clean(v):
    if pd.isna(v): return ''
    return str(v).replace('"', '&quot;')

def detect_internal(email):
    if pd.isna(email): return False
    return str(email).split('@')[-1].lower() in ('pipelovers.net', 'curseduca.com')

def turma_to_company_fallback(turma):
    """Fallback para extrair empresa do campo Turmas (lógica antiga, usada só em aulas)."""
    if pd.isna(turma): return None
    GENERIC = {'Aplicativo','Full Pass','Pré-vendas','Gestão','Executivos',
                'Canais','Class','Novo grupo - Priscila','Pré Vendas'}
    for p in [x.strip() for x in str(turma).split(',')]:
        m1 = re.match(r'^\d+ - \d+ - (.+)$', p)
        if m1: return m1.group(1).strip()
        m2 = re.match(r'^\d+ - (.+)$', p)
        if m2:
            name = m2.group(1).strip()
            if name not in GENERIC: return name
    return None

def empresa_from_domain(email):
    if pd.isna(email): return ''
    d = str(email).lower()
    domain_map = {
        'sidrasul': 'Sidrasul Sistemas Hidráulicos Ltda',
        'bmchyundai': 'BMC Hyundai',
        'cartrom': 'CARTROM',
        'medika': 'Medika',
        'tecnogera': 'Tecnogera',
        'becomex': 'Becomex',
        'progic': 'Progic',
        'premier': 'Grupo Premier Alimentos',
    }
    for key, name in domain_map.items():
        if key in d: return name
    return ''

# ── LEITURA DOS ARQUIVOS ─────────────────────────────────────
grupos  = read_csv(BASE / 'grupos_acesso.csv')
members = read_csv(BASE / 'members-report.csv')
clientes = read_csv(BASE / 'clientes.csv')
report  = read_csv(BASE / 'consumo.csv')

# ── NORMALIZAÇÃO DO grupos_acesso.csv ────────────────────────
# Detecta colunas de código e nome da empresa
col_codigo = next((c for c in grupos.columns if 'código' in c.lower() or 'codigo' in c.lower() or c.strip().lower() in ('id','code','cod')), None)
col_empresa = next((c for c in grupos.columns if 'empresa' in c.lower() or 'nome' in c.lower()), None)
col_csm_ga = next((c for c in grupos.columns if 'csm' in c.lower()), None)
col_status = next((c for c in grupos.columns if 'status' in c.lower() or 'situação' in c.lower() or 'situacao' in c.lower()), None)

if col_codigo is None or col_empresa is None:
    raise ValueError(f"grupos_acesso.csv: não encontrei colunas de código e empresa. Colunas disponíveis: {list(grupos.columns)}")

grupos = grupos.rename(columns={col_codigo: 'grupo_code', col_empresa: 'empresa_ga'})
if col_csm_ga:
    grupos = grupos.rename(columns={col_csm_ga: 'csm_ga'})
if col_status:
    grupos = grupos.rename(columns={col_status: 'status_ga'})

grupos['grupo_code'] = pd.to_numeric(grupos['grupo_code'], errors='coerce')
grupos = grupos.dropna(subset=['grupo_code'])
grupos['grupo_code'] = grupos['grupo_code'].astype(int)

# Remove trilhas internas
grupos = grupos[~grupos['grupo_code'].isin(TRILHAS_INTERNAS)].copy()

# ── NORMALIZAÇÃO DO members-report.csv ───────────────────────
members['email_lower'] = members['Email'].str.lower().str.strip()

# Extrair todos os códigos de grupo do campo Turmas
def extract_group_codes(turma_str):
    if pd.isna(turma_str): return []
    codes = []
    for part in str(turma_str).split(','):
        part = part.strip()
        m = re.match(r'^(\d+)\s*-', part)
        if m:
            code = int(m.group(1))
            if code not in TRILHAS_INTERNAS:
                codes.append(code)
    return codes

members['group_codes'] = members['Turmas'].apply(extract_group_codes)
members['acessou'] = members['Último acesso'] != 'Nunca acessou'

# ── JOIN: members × grupos_acesso ────────────────────────────
# Expande cada membro por código de grupo, depois faz join
rows_exp = []
for _, row in members.iterrows():
    for code in row['group_codes']:
        rows_exp.append({'email_lower': row['email_lower'], 'grupo_code': code,
                         'Nome': row.get('Nome',''), 'Email': row.get('Email',''),
                         'Último acesso': row.get('Último acesso',''),
                         'Situação': row.get('Situação',''),
                         'Data de criação': row.get('Data de criação',''),
                         'Turmas': row.get('Turmas',''),
                         'acessou': row['acessou']})

members_exp = pd.DataFrame(rows_exp) if rows_exp else pd.DataFrame(
    columns=['email_lower','grupo_code','Nome','Email','Último acesso','Situação','Data de criação','Turmas','acessou'])

# Join com grupos
members_joined = members_exp.merge(grupos[['grupo_code','empresa_ga'] +
    (['csm_ga'] if 'csm_ga' in grupos.columns else []) +
    (['status_ga'] if 'status_ga' in grupos.columns else [])],
    on='grupo_code', how='inner')

# ── CSM via clientes.csv ──────────────────────────────────────
company_csm = {}
for _, r in clientes[['Empresa','CSM']].dropna(subset=['Empresa']).iterrows():
    company_csm[r['Empresa'].strip().lower()] = r['CSM']

def get_csm(name):
    if pd.isna(name) or str(name).strip() == '': return ''
    nl = str(name).strip().lower()
    if nl in company_csm: return str(company_csm[nl])
    for k, v in company_csm.items():
        if nl in k or k in nl: return str(v)
    return ''

# Preferência: CSM do grupos_acesso → CSM do clientes.csv
if 'csm_ga' in members_joined.columns:
    members_joined['CSM'] = members_joined['csm_ga'].fillna('')
    mask_no_csm = members_joined['CSM'] == ''
    members_joined.loc[mask_no_csm, 'CSM'] = members_joined.loc[mask_no_csm, 'empresa_ga'].apply(get_csm)
else:
    members_joined['CSM'] = members_joined['empresa_ga'].apply(get_csm)

# ── DEFINIÇÃO DE REIMPLANTADO ─────────────────────────────────
# Empresa reimplantada = grupo com ≥1 login
empresas_com_login = set(
    members_joined[members_joined['acessou']]['empresa_ga'].unique()
)

# Todos os grupos conhecidos
todos_grupos = grupos['empresa_ga'].unique()

# Filtragem de churn
if not INCLUIR_CHURN_REIMPLANTADAS and 'status_ga' in grupos.columns:
    status_bad = {'churn', 'inativo', 'inativa', 'cancelado'}
    grupos_ativos = grupos[~grupos['status_ga'].str.lower().str.strip().isin(status_bad)]['empresa_ga'].unique()
    empresas_reimplantadas = [e for e in empresas_com_login if e in set(grupos_ativos)]
    empresas_pendentes = [e for e in grupos_ativos if e not in empresas_com_login]
else:
    empresas_reimplantadas = list(empresas_com_login)
    empresas_pendentes = [e for e in todos_grupos if e not in empresas_com_login]

empresas_reimplantadas = sorted(empresas_reimplantadas)
empresas_pendentes = sorted(empresas_pendentes)

# ── KPIs POR EMPRESA ─────────────────────────────────────────
def to_rows_joined(df_sub):
    rows = []
    for _, r in df_sub.drop_duplicates(subset=['email_lower','empresa_ga']).iterrows():
        csm = clean(r.get('CSM',''))
        rows.append({
            'nome': clean(r.get('Nome','')),
            'email': clean(r.get('Email','')),
            'empresa': clean(r.get('empresa_ga','')),
            'csm': csm,
            'ultimo_acesso': clean(r.get('Último acesso','')),
            'situacao': clean(r.get('Situação','')),
            'turmas': clean(r.get('Turmas','')),
            'data_criacao': clean(r.get('Data de criação','')),
        })
    return rows

reimpl_df = members_joined[members_joined['empresa_ga'].isin(set(empresas_reimplantadas))].copy()
pendentes_df = members_joined[members_joined['empresa_ga'].isin(set(empresas_pendentes))].copy()

# Usuários que acessaram vs não
acessaram_df = reimpl_df[reimpl_df['acessou']].copy()
nao_acessaram_df = reimpl_df[~reimpl_df['acessou']].copy()

total_r = reimpl_df['email_lower'].nunique()
acessaram_count = acessaram_df['email_lower'].nunique()

por_empresa = []
for emp in empresas_reimplantadas:
    df_e = reimpl_df[reimpl_df['empresa_ga'] == emp]
    acc = df_e[df_e['acessou']]['email_lower'].nunique()
    tot = df_e['email_lower'].nunique()
    csm_mode = df_e['CSM'].mode()
    por_empresa.append({
        'empresa': emp,
        'csm': csm_mode.iloc[0] if len(csm_mode) else '',
        'total': tot, 'acessaram': acc,
        'nao_acessaram': tot - acc,
        'pct': round(acc / tot * 100, 1) if tot else 0
    })

# Por CSM
csm_all = sorted(set(members_joined['CSM'].unique()) - {''})
por_csm = []
for csm in csm_all:
    r = reimpl_df[reimpl_df['CSM'] == csm]
    nr = pendentes_df[pendentes_df['CSM'] == csm]
    acc = r[r['acessou']]['email_lower'].nunique()
    tot = r['email_lower'].nunique()
    emps = set(r['empresa_ga'].unique())
    por_csm.append({
        'csm': csm, 'empresas': len(emps), 'total': tot,
        'acessaram': acc, 'nao_acessaram': tot - acc,
        'pct': round(acc / tot * 100, 1) if tot else 0,
        'pendentes': nr['empresa_ga'].nunique()
    })

# Não encontrados: membros sem grupo reconhecido em grupos_acesso
emails_com_grupo = set(members_joined['email_lower'].unique())
nao_enc_df = members[~members['email_lower'].isin(emails_com_grupo)].copy()
nao_enc_df['empresa_ga'] = ''
nao_enc_df['CSM'] = ''

def to_rows_members(df_sub):
    rows = []
    for _, r in df_sub.iterrows():
        rows.append({
            'nome': clean(r.get('Nome','')),
            'email': clean(r.get('Email','')),
            'empresa': clean(r.get('empresa_ga', r.get('Nome da Empresa',''))),
            'csm': clean(r.get('CSM','')),
            'ultimo_acesso': clean(r.get('Último acesso','')),
            'situacao': clean(r.get('Situação','')),
            'turmas': clean(r.get('Turmas','')),
            'data_criacao': clean(r.get('Data de criação','')),
        })
    return rows

# ── ABA AULAS ────────────────────────────────────────────────
report['email_lower'] = report['Email'].str.lower().str.strip()
report['is_internal'] = report['email_lower'].apply(detect_internal)
report['empresa_turma_fb'] = report['Turmas'].apply(turma_to_company_fallback)

# Tenta enriquecer com grupos_acesso também
report_codes = report['Turmas'].apply(extract_group_codes)
report['primeiro_code'] = report_codes.apply(lambda x: x[0] if x else None)
report_ga = report.merge(
    grupos[['grupo_code','empresa_ga']].rename(columns={'empresa_ga': 'empresa_ga_aulas'}),
    left_on='primeiro_code', right_on='grupo_code', how='left'
)

report_ga['empresa_final'] = (
    report_ga['empresa_ga_aulas'].fillna('').where(report_ga['empresa_ga_aulas'].notna() & (report_ga['empresa_ga_aulas'] != ''))
    .combine_first(report_ga['empresa_turma_fb'])
    .combine_first(report_ga['email_lower'].apply(empresa_from_domain))
)
report_ga.loc[report_ga['empresa_final'].isna() & report_ga['is_internal'], 'empresa_final'] = 'PipeLovers'
report_ga['empresa_final'] = report_ga['empresa_final'].fillna('').str.replace(r'^[Cc]artrom$', 'CARTROM', regex=True)

report_ga['CSM'] = report_ga['empresa_final'].apply(get_csm)
report_ga.loc[(report_ga['CSM'] == '') & report_ga['is_internal'], 'CSM'] = 'Gunther Weissbock'

report_ga['data_compra_dt'] = pd.to_datetime(report_ga['Data da compra'], format='%d/%m/%Y', errors='coerce')
report_ga['mes'] = report_ga['data_compra_dt'].dt.strftime('%Y-%m').fillna('')

rows_aulas = []
for _, row in report_ga.iterrows():
    rows_aulas.append({
        'nome': clean(row['Nome']), 'email': clean(row['Email']),
        'empresa': clean(row['empresa_final']), 'csm': clean(row['CSM']),
        'conteudo': clean(row['Conteúdo']), 'turma': clean(row['Turmas']),
        'progresso': clean(row['Progresso']), 'matricula': clean(row['Matrícula']),
        'data_compra': clean(row['Data da compra']), 'mes': row['mes'],
        'situacao': clean(row['Situação do membro'])
    })

por_empresa_aulas = []
for emp, df_e in report_ga[report_ga['empresa_final'] != ''].groupby('empresa_final'):
    csm_mode = df_e['CSM'].mode()
    por_empresa_aulas.append({
        'empresa': str(emp),
        'csm': csm_mode.iloc[0] if len(csm_mode) else '',
        'total_aulas': len(df_e),
        'usuarios': df_e['email_lower'].nunique(),
        'conteudos': df_e['Conteúdo'].nunique()
    })
por_empresa_aulas.sort(key=lambda x: -x['total_aulas'])

top_conteudos = sorted(
    [{'conteudo': str(c), 'total': len(df_c)} for c, df_c in report_ga.groupby('Conteúdo')],
    key=lambda x: -x['total']
)
meses_aulas = sorted([m for m in report_ga['mes'].dropna().unique() if m])

summary_aulas = {
    'total_aulas': len(report_ga),
    'unique_users': report_ga['email_lower'].nunique(),
    'unique_empresas': report_ga[report_ga['empresa_final'] != '']['empresa_final'].nunique(),
    'unique_conteudos': report_ga['Conteúdo'].nunique()
}

# ── INJETA NO HTML ────────────────────────────────────────────
now = pd.Timestamp.now().strftime('%d/%m/%Y')

js = (
    f'var UPD={json.dumps(now)};\n'
    + 'var SUMMARY=' + json.dumps({
        'empresas_reimplantadas': len(empresas_reimplantadas),
        'total_usuarios_reimpl': total_r,
        'acessaram': acessaram_count,
        'nao_acessaram': total_r - acessaram_count,
        'pct_adocao': round(acessaram_count / total_r * 100, 1) if total_r else 0,
        'nao_encontrados': len(nao_enc_df),
        'nao_reimplantados': len(empresas_pendentes),
        'gerado_em': now
    }) + ';\n'
    + 'var POR_EMPRESA=' + json.dumps(por_empresa, ensure_ascii=False) + ';\n'
    + 'var POR_CSM=' + json.dumps(por_csm, ensure_ascii=False) + ';\n'
    + 'var ACESSARAM=' + json.dumps(to_rows_joined(acessaram_df), ensure_ascii=False) + ';\n'
    + 'var NAO_ACESSARAM=' + json.dumps(to_rows_joined(nao_acessaram_df), ensure_ascii=False) + ';\n'
    + 'var NAO_REIMPL=' + json.dumps(to_rows_joined(pendentes_df), ensure_ascii=False) + ';\n'
    + 'var NAO_ENC=' + json.dumps(to_rows_members(nao_enc_df), ensure_ascii=False) + ';\n'
    + 'var SUMMARY_AULAS=' + json.dumps(summary_aulas, ensure_ascii=False) + ';\n'
    + 'var ROWS_AULAS=' + json.dumps(rows_aulas, ensure_ascii=False) + ';\n'
    + 'var POR_EMPRESA_AULAS=' + json.dumps(por_empresa_aulas, ensure_ascii=False) + ';\n'
    + 'var TOP_CONTEUDOS=' + json.dumps(top_conteudos, ensure_ascii=False) + ';\n'
    + 'var MESES_AULAS=' + json.dumps(meses_aulas, ensure_ascii=False) + ';\n'
)

html = (BASE / 'index.html').read_text(encoding='utf-8')
marker = '/* ══ DATA ══════════════════════════════════════════════════════ */'
end_marker = '/* ══ HELPERS'
start = html.index(marker) + len(marker)
end = html.index(end_marker)
html = html[:start] + '\n' + js + html[end:]
(BASE / 'index.html').write_text(html, encoding='utf-8')

print(f'✅ index.html atualizado — {now}')
print(f'   Empresas reimplantadas : {len(empresas_reimplantadas)} | Pendentes: {len(empresas_pendentes)}')
print(f'   Usuários reimplantados : {total_r} | Acessaram: {acessaram_count}')
print(f'   Aulas registradas      : {len(report_ga)} | Usuários únicos: {report_ga["email_lower"].nunique()} | Conteúdos: {report_ga["Conteúdo"].nunique()}')
