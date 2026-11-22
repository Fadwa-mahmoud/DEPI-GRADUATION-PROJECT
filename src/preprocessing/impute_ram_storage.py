import argparse, ast, json, re, zipfile, os
import numpy as np, pandas as pd
FX = {'$': 1.0, '€': 1.08, '£': 1.27, '₹': 0.012, 'C$': 0.73}
SIG, ALPHA = (0.5, 2.0)

# 1. Clean model names so different spellings match.
def squash(s):
    s = str(s).lower().replace('+', ' plus ')
    s = re.sub('\\(.*?\\)', '', s)
    s = s.replace('galaxy', '')
    s = re.sub('\\b(5g|4g|lte|dual sim|dual-sim)\\b', '', s)
    return re.sub('[^a-z0-9]', '', s)

# 2. Read storage and RAM combinations from reference datasets.
def variants(s):
    res = []
    for part in str(s).split(','):
        m = re.match('\\s*(\\d+(?:\\.\\d+)?)\\s*(GB|TB|MB)\\s+(\\d+(?:\\.\\d+)?)\\s*(GB|MB)\\s*RAM', part)
        if m:
            st = float(m.group(1)) * {'GB': 1, 'TB': 1024, 'MB': 1 / 1024}[m.group(2)]
            ra = float(m.group(3)) * {'GB': 1, 'MB': 1 / 1024}[m.group(4)]
            res.append((st, ra))
    return res

# 3. Convert reference prices to a common currency.
def price_usd(txt):
    if not isinstance(txt, str):
        return np.nan
    t = txt.replace('\u2009', ' ')
    if 'C$' in t:
        m = re.search('C\\$\\s*([\\d,\\.]+)', t)
        if m:
            return float(m.group(1).replace(',', '')) * FX['C$']
    for cur in ['$', '€', '£', '₹']:
        m = re.search(re.escape(cur) + '\\s*([\\d,\\.]+)', t)
        if m:
            try:
                return float(m.group(1).replace(',', '')) * FX[cur]
            except ValueError:
                pass
    m = re.search('About\\s+([\\d,\\.]+)\\s*EUR', t)
    return float(m.group(1).replace(',', '')) * FX['€'] if m else np.nan

# 4. Convert storage/RAM units to GB.
def to_gb(txt):
    m = re.match('\\s*(\\d+(?:\\.\\d+)?)\\s*(TB|GB|MB|KB)', str(txt), re.I)
    return float(m.group(1)) * {'TB': 1024, 'GB': 1, 'MB': 1 / 1024, 'KB': 1 / 1024 ** 2}[m.group(2).upper()] if m else np.nan

# 5. Read phone specifications from MobileDokan.
def dokan_rows(dokan_zip):
    """MobileDokan (Jul-2025): one row per (model, storage) SKU. Rumored/upcoming rows are dropped (their specs are guesses).
    price_variants is NOT used (mixed regions/currencies)."""
    with zipfile.ZipFile(dokan_zip) as z:
        name = sorted((n for n in z.namelist() if n.endswith('.csv')))[-1]
        b = pd.read_csv(z.open(name))
    rd = b.release_date.fillna('')
    st = b.status.fillna('')
    bad = rd.str.contains('not announced|exp\\.|expected|rumou?r|coming|tba|upcoming', case=False) | st.str.contains('rumo|upcom|expect', case=False)
    b = b[~bad & b.device_type.fillna('').str.contains('smart', case=False)]
    out = []
    for _, x in b.iterrows():
        sto, ram = (to_gb(x.internal_storage), to_gb(x.ram))
        if pd.notna(sto) and pd.notna(ram):
            out.append(dict(key=squash(f'{x.brand} {x.model}'), src='dokan', storage=sto, ram=ram, price_usd=np.nan))
    return out
MODS = {'pro', 'plus', 'max', 'ultra', 'fe', 'lite', 'mini', 'edge', 'neo', 'turbo', 'air', 'se', 'fold', 'flip', 'note', 'prime', 'power', 'play', 'active', 'go'}
VALID_ST = {16, 32, 64, 128, 256, 512, 1024}
VALID_RAM = {1, 2, 3, 4, 6, 8, 12, 16, 18, 24}

def _toks(t):
    t = str(t).lower().replace('+', ' plus ')
    return [w for w in re.findall('[a-z0-9]+', t) if w not in ('galaxy', '5g', '4g', 'lte')]

# 6. Extract storage and RAM from Jumia product titles.
def parse_storage_ram(desc):
    """Jumia titles: '128GB Storage, 6GB RAM' | '256GB/8GB' | '12GB/256GB' | '512GB, 12GB RAM'.
    NOTE: the product_storage / product_ram columns of the Jumia file are wrong (ram == storage), so we re-parse the title."""
    d = str(desc)
    ram = re.search('(\\d+)\\s*GB\\s*RAM', d, re.I)
    sto = re.search('(\\d+)\\s*(?:GB|TB)\\s*(?:Storage|ROM)', d, re.I)
    pair = re.search('(\\d+)\\s*GB\\s*/\\s*(\\d+)\\s*(GB|TB)', d, re.I)
    r = s_ = None
    if ram:
        r = float(ram.group(1))
    if sto:
        s_ = float(sto.group(1))
    if pair and (r is None or s_ is None):
        a, b = (float(pair.group(1)), float(pair.group(2)) * (1024 if pair.group(3).upper() == 'TB' else 1))
        lo, hi = (min(a, b), max(a, b))
        r = r if r is not None else lo
        s_ = s_ if s_ is not None else hi
    if r is None or s_ is None:
        nums = [float(x) for x in re.findall('(\\d+)\\s*GB', d, re.I)]
        if r is not None and s_ is None:
            c = [n for n in nums if n in VALID_ST and n != r]
            s_ = max(c) if c else None
    if s_ == 1:
        s_ = 1024.0
    tb = re.search('(\\d)\\s*TB', d, re.I)
    if tb and s_ is None:
        s_ = float(tb.group(1)) * 1024
    if r in VALID_RAM and s_ in VALID_ST and (r <= s_) and (not r == s_):
        return (s_, r)
    return None

# 7. Match a Jumia listing to one of our known model names.
def match_key(desc, brand, model_keys):
    t = _toks(desc)
    best = None
    for mk in model_keys:
        kt = _toks(mk)
        n = len(kt)
        cands = [kt]
        if len(kt) >= 3 and kt[0] == str(brand).lower():
            cands.append(kt[1:])
        for c in cands:
            for i in range(len(t) - len(c) + 1):
                if t[i:i + len(c)] == c:
                    nxt = t[i + len(c)] if i + len(c) < len(t) else ''
                    if nxt in MODS and nxt != c[-1]:
                        continue
                    if len(c) < len(kt) and kt[0] != str(brand).lower():
                        continue
                    if best is None or len(c) > best[0]:
                        best = (len(c), mk)
    return best[1] if best else None

# 8. Keep usable Jumia phone listings as extra reference variants.
def jumia_rows(csv_path, model_keys):
    j = pd.read_csv(csv_path)
    j['p'] = pd.to_numeric(j.product_price.astype(str).str.replace(',', ''), errors='coerce')
    j = j[j.p >= 1500].drop_duplicates('product_description')
    out = []
    for _, x in j.iterrows():
        sr = parse_storage_ram(x.product_description)
        if not sr:
            continue
        mk = match_key(x.product_description, x.product_brand, model_keys)
        if mk:
            out.append(dict(key=squash(mk), src='jumia', storage=sr[0], ram=sr[1], price_usd=np.nan, price_egp=x.p))
    return out

# 9. Read used-iPhone prices; this file adds prices, not RAM values.
def iphone_xlsx_anchor_rows(xlsx_path):
    """Used-iPhone listings (Model, Storage, Price in EGP) -> extra price anchors for storage choice. No RAM in this file."""
    x = pd.read_excel(xlsx_path)
    return pd.DataFrame(dict(model_key='apple ' + x.Model.astype(str).str.lower().str.strip().str.replace('iphone(\\d)', 'iphone \\1', regex=True), brand='apple', storage_gb=x.Storage.astype(float), ram_gb=np.nan, price=x.Price.astype(float), price_missing=False, price_suspicious=False, price_placeholder=False))

# 10. Combine all reference sources into one model/specification table.
def build_reference(json_zip, allphones_zip, gsm_zip, dokan_zip=None, jumia_csv=None, model_keys=None):
    rows, base = ([], {})
    with zipfile.ZipFile(json_zip) as z:
        j = json.load(z.open('data.json'))
        pm = pd.read_csv(z.open('processed_data2.csv'))
    for x in j:
        k = squash(x['phone_model'])
        pu = price_usd(x['price'])
        for st, ra in variants(x['specs'].get('Memory', {}).get('Internal')):
            rows.append(dict(key=k, src='json', storage=st, ram=ra, price_usd=np.nan))
        if not np.isnan(pu):
            base.setdefault(k, []).append(pu)
    with zipfile.ZipFile(allphones_zip) as z:
        d = pd.read_csv(z.open('AllPhones.csv'))
    for _, x in d.iterrows():
        k = squash(x.Name)
        for st, ra in variants(x.Memory_Internalmemory):
            rows.append(dict(key=k, src='allphones', storage=st, ram=ra, price_usd=np.nan))
        pu = price_usd(x.Price)
        if not np.isnan(pu):
            base.setdefault(k, []).append(pu)
        if isinstance(x.Prices, str):
            try:
                lst = ast.literal_eval(x.Prices)
            except Exception:
                lst = []
            for dd in lst:
                for kk, v in dd.items():
                    for st, ra in variants(kk):
                        rows.append(dict(key=k, src='allphones_pv', storage=st, ram=ra, price_usd=price_usd(v)))
    for _, x in pm.iterrows():
        try:
            st, ra = (float(x.storage), float(x.ram))
        except (TypeError, ValueError):
            continue
        rows.append(dict(key=squash(x.phone_model), src='processed2', storage=1024.0 if st == 1000 else st, ram=ra, price_usd=x.price_usd))
    with zipfile.ZipFile(gsm_zip) as z:
        name = [n for n in z.namelist() if n.endswith('Cleaned - Final/WholeDataset.csv')][0]
        w = pd.read_csv(z.open(name))
    for _, x in w.iterrows():
        try:
            st, ra = (float(x.Storage), float(x.RAM))
        except (TypeError, ValueError):
            continue
        rows.append(dict(key=squash(x.Name), src='whole', storage=st, ram=ra, price_usd=np.nan))
        if pd.notna(x.Price):
            base.setdefault(squash(x.Name), []).append(float(x.Price) * FX['₹'])
    if dokan_zip:
        rows += dokan_rows(dokan_zip)
    if jumia_csv:
        rows += jumia_rows(jumia_csv, model_keys)
    ref = pd.DataFrame(rows)
    if 'price_egp' not in ref:
        ref['price_egp'] = np.nan
    ref = ref[(ref.storage >= 1) & (ref.ram >= 0.5)]
    V = ref.groupby(['key', 'storage', 'ram']).agg(n_rows=('src', 'size'), n_src=('src', lambda x: x.str.replace('_pv', '').nunique()), ref_price=('price_usd', 'median'), ref_egp=('price_egp', 'median')).reset_index()
    V['pop'] = V.n_rows / V.groupby('key').n_rows.transform('sum')
    return ({k: d.reset_index(drop=True) for k, d in V.groupby('key')}, {k: float(np.median(v)) for k, v in base.items()}, V)

# 11. Identify prices that should not be used.
def bad_price(r):
    return bool(r.price_missing or r.price_suspicious or r.price_placeholder or (not np.isfinite(r.price)) or (r.price <= 0))

# 12. Learn price patterns from training rows only.
def fit(train, VK, base):
    tr = train[train.storage_gb.notna() & ~train.price_missing & ~train.price_suspicious & ~train.price_placeholder & (train.model_key != 'unknown')].copy()
    tr['k'] = tr.model_key.map(squash)
    tr['lp'] = np.log(tr.price)
    tr['ls'] = np.log2(tr.storage_gb)
    d = tr.groupby('k').filter(lambda x: x.storage_gb.nunique() >= 2)
    xs = d.ls - d.groupby('k').ls.transform('mean')
    ys = d.lp - d.groupby('k').lp.transform('mean')
    beta = float(np.clip((xs * ys).sum() / (xs ** 2).sum(), 0.1, 0.6))
    offs = []
    for _, r in tr.iterrows():
        v, b = (VK.get(r.k), base.get(r.k))
        if v is None or b is None:
            continue
        offs.append((r.brand, r.lp - np.log(b * 2 ** (beta * (r.ls - np.log2(v.storage.min()))))))
    o = pd.DataFrame(offs, columns=['brand', 'off'])
    jo = []
    for _, r in tr.iterrows():
        v = VK.get(r.k)
        if v is None:
            continue
        m = v[(v.storage == r.storage_gb) & v.ref_egp.notna()]
        if len(m):
            jo.append((r.brand, r.lp - np.log(m.ref_egp.iloc[0])))
    jo = pd.DataFrame(jo, columns=['brand', 'off'])
    return dict(tr=tr, beta=beta, boff=o.groupby('brand').off.median().to_dict(), gm=float(o.off.median()), joff=jo.groupby('brand').off.median().to_dict() if len(jo) else {}, jgm=float(jo.off.median()) if len(jo) else None)

# 13. Estimate the expected price for each possible storage size.
def storage_expected(k, cands, vk, P, brand, base):
    trk = P['tr'][P['tr'].k == k]
    med = trk.groupby('storage_gb').lp.median()
    E = {}
    for s in cands:
        if s in med.index:
            E[s] = (med[s], 'my_data')
            continue
        if len(med):
            s0 = med.index[np.abs(np.log2(med.index) - np.log2(s)).argmin()]
            rj = vk[vk.storage == s].ref_egp.dropna()
            rj0 = vk[vk.storage == s0].ref_egp.dropna()
            rp = vk[vk.storage == s].ref_price.dropna()
            rp0 = vk[vk.storage == s0].ref_price.dropna()
            if len(rj) and len(rj0):
                E[s] = (med[s0] + np.log(rj.iloc[0] / rj0.iloc[0]), 'my_data+jumia_ratio')
            elif len(rp) and len(rp0):
                E[s] = (med[s0] + np.log(rp.iloc[0] / rp0.iloc[0]), 'my_data+ref_ratio')
            else:
                E[s] = (med[s0] + P['beta'] * (np.log2(s) - np.log2(s0)), 'my_data+slope')
            continue
        rj = vk[vk.storage == s].ref_egp.dropna()
        if len(rj) and P.get('jgm') is not None:
            E[s] = (np.log(rj.iloc[0]) + P['joff'].get(brand, P['jgm']), 'jumia_price')
            continue
        b = base.get(k)
        if b is None:
            E[s] = (np.nan, 'none')
            continue
        off = P['boff'].get(brand, P['gm'])
        rp = vk[vk.storage == s].ref_price.dropna()
        if len(rp):
            E[s] = (np.log(rp.iloc[0]) + off, 'ref_price')
        else:
            E[s] = (np.log(b * 2 ** (P['beta'] * (np.log2(s) - np.log2(vk.storage.min())))) + off, 'ref_base+slope')
    return E

# 14. Fill missing storage/RAM for one listing.
def impute(r, P, VK, base):
    k = squash(r.model_key)
    out = dict(st=np.nan, ra=np.nan, st_src=None, ra_src=None, st_conf=None, ra_conf=None, st_post=np.nan, ra_post=np.nan, price_used=False, matched=False)
    if r.model_key == 'unknown' or k not in VK:
        return out
    out['matched'] = True
    vk = VK[k]
    st_known, ra_known = (pd.notna(r.storage_gb), pd.notna(r.ram_gb))
    if st_known:
        vk = vk[vk.storage == r.storage_gb]
    vr = VK[k][VK[k].ram == r.ram_gb] if ra_known else VK[k]
    if not st_known:
        cands = sorted((vk[vk.ram == r.ram_gb] if ra_known else vk).storage.unique())
        if len(cands) == 1:
            ns = vk[vk.storage == cands[0]].n_src.max()
            out.update(st=cands[0], st_src='ref_unique' if ns >= 2 else 'ref_unique_single_source', st_conf='high' if ns >= 2 else 'medium', st_post=1.0 if ns >= 2 else 0.8)
        elif len(cands) > 1:
            trk = P['tr'][P['tr'].k == k]
            cnt = trk.storage_gb.value_counts()
            share = vk.groupby('storage')['pop'].sum()
            share = share / share.sum()
            prior = {s: (cnt.get(s, 0) + ALPHA * share.get(s, 0) + 0.001) / (len(trk) + ALPHA) for s in cands}
            if bad_price(r):
                sc = {s: -np.log(prior[s]) for s in cands}
                used, src = (False, 'prior_only')
            else:
                E = storage_expected(k, cands, vk, P, r.brand, base)
                lp = np.log(r.price)
                sc = {s: (abs(lp - E[s][0]) / SIG if not np.isnan(E[s][0]) else 0) - np.log(prior[s]) for s in cands}
                srcs = {E[s][1] for s in cands}
                used = True
                src = 'price+prior:' + ('my_data' if 'my_data' in srcs else sorted(srcs)[0])
            z = np.array([sc[s] for s in cands])
            p = np.exp(-(z - z.min()))
            p /= p.sum()
            i = int(p.argmax())
            out.update(st=cands[i], st_src=src, st_post=float(p[i]), price_used=used, st_conf='medium' if p[i] >= 0.7 else 'low')
    else:
        out.update(st=r.storage_gb, st_src='title', st_conf='known', st_post=1.0)
    if not ra_known:
        rams = vr.ram.unique()
        if len(rams) == 1:
            ns = vr.n_src.max()
            out.update(ra=rams[0], ra_src='ref_unique_per_model' if ns >= 2 else 'ref_unique_single_source', ra_conf='high' if ns >= 2 else 'medium', ra_post=1.0 if ns >= 2 else 0.8)
        else:
            s = out['st']
            sub = vr[vr.storage == s] if pd.notna(s) else vr.iloc[0:0]
            if len(sub) == 0:
                sub = vr
            if sub.ram.nunique() == 1:
                out.update(ra=sub.ram.iloc[0], ra_src='ref_unique_given_storage', ra_conf='high' if out['st_conf'] in ('known', 'high') else out['st_conf'], ra_post=out['st_post'])
            else:
                w = sub.groupby('ram')['pop'].sum()
                w = w / w.sum()
                out.update(ra=w.idxmax(), ra_src='ref_popularity', ra_conf='low', ra_post=float(w.max()))
    else:
        out.update(ra=r.ram_gb, ra_src='title', ra_conf='known', ra_post=1.0)
    return out

# 15. Apply the filling process to a whole dataset.
def apply(df, P, VK, base):
    o = pd.DataFrame([impute(r, P, VK, base) for _, r in df.iterrows()], index=df.index)
    df = df.copy()
    df['storage_gb_imp'] = o.st
    df['ram_gb_imp'] = o.ra
    df['storage_imp_src'] = o.st_src
    df['storage_imp_conf'] = o.st_conf
    df['storage_imp_post'] = o.st_post.round(3)
    df['ram_imp_src'] = o.ra_src
    df['ram_imp_conf'] = o.ra_conf
    df['ram_imp_post'] = o.ra_post.round(3)
    df['imp_price_used'] = o.price_used
    df['ref_matched'] = o.matched
    return df



# 16. Run the full process and save the output files.
if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for a in ['train', 'val', 'json_zip', 'allphones_zip', 'gsm_zip']:
        ap.add_argument('--' + a, required=True)
    ap.add_argument('--dokan_zip', default=None)
    ap.add_argument('--jumia_csv', default=None)
    ap.add_argument('--iphone_xlsx', default=None)
    ap.add_argument('--out_dir', default='out')


    A = ap.parse_args()
    os.makedirs(A.out_dir, exist_ok=True)
    tr, va = (pd.read_csv(A.train), pd.read_csv(A.val))
    mkeys = sorted((set(tr.model_key) | set(va.model_key)) - {'unknown'})
    VK, base, V = build_reference(A.json_zip, A.allphones_zip, A.gsm_zip, A.dokan_zip, A.jumia_csv, mkeys)
    fit_df = tr

    if A.iphone_xlsx:
        ex = iphone_xlsx_anchor_rows(A.iphone_xlsx)
        seen = set(map(tuple, tr[['model_key', 'storage_gb', 'price']].dropna().values))
        dup = np.array([tuple(r) in seen for r in ex[['model_key', 'storage_gb', 'price']].values])
        fit_df = pd.concat([tr, ex[~dup]], ignore_index=True)
    P = fit(fit_df, VK, base)

    tr2, va2 = (apply(tr, P, VK, base), apply(va, P, VK, base))
    tr2.to_csv(os.path.join(A.out_dir, 'stage2_train_df_imputed.csv'), index=False)
    va2.to_csv(os.path.join(A.out_dir, 'stage2_val_df_imputed.csv'), index=False)
    V.to_csv(os.path.join(A.out_dir, 'reference_variants.csv'), index=False)


    al = pd.concat([tr2, va2])
    um = al[~al.ref_matched & (al.model_key != 'unknown')].model_key.value_counts()
    um.rename_axis('model_key').reset_index(name='rows').to_csv(os.path.join(A.out_dir, 'unmatched_models.csv'), index=False)
    print('beta', round(P['beta'], 3))
    print(al.ref_matched.value_counts())
