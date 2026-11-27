import re, sys, io, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'foods.js')
src = open(path, encoding='utf-8').read()

STR = {'room', 'fridge', 'frozen'}


def split_args(s, i):
    """从 s[i] 开始（F( 之后的第一个字符）按顶层逗号切参数，返回 (args, 结束位置)。"""
    args, cur, depth, j, n = [], '', 0, i, len(s)
    while j < n:
        ch = s[j]
        if ch == "'":
            k = j + 1
            while k < n and s[k] != "'":
                k += 2 if s[k] == '\\' else 1
            cur += s[j:k + 1]
            j = k + 1
            continue
        if ch in '[({':
            depth += 1
        elif ch in '])}':
            if depth == 0 and ch == ')':
                args.append(cur.strip())
                return args, j
            depth -= 1
        elif ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
            j += 1
            continue
        cur += ch
        j += 1
    return args, j


items, problems = [], []
pos = 0
while True:
    m = re.search(r"\bF\('", src[pos:])
    if not m:
        break
    start = pos + m.end() - 1
    args, end = split_args(src, start)
    pos = end + 1

    def unq(a):
        return a[1:-1] if len(a) >= 2 and a[0] == "'" and a[-1] == "'" else None

    fid = unq(args[0]) if args else None
    if fid is None:
        continue
    name = unq(args[1])
    cat = unq(args[2])
    alias_ok = args[3].startswith('[')
    py = args[4] if len(args) > 4 else ''
    py_ok = (len(py) >= 2 and py[0] == "'" and py[-1] == "'")
    days = args[5:8]
    default = unq(args[8]) if len(args) > 8 else None

    if not py_ok:
        problems.append(f'{fid}: 第5个参数不是拼音串 -> {py[:30]}')
    if not alias_ok:
        problems.append(f'{fid}: 第4个参数不是别名数组')
    if len(days) != 3:
        problems.append(f'{fid}: 天数参数数量 {len(days)}')
    if default not in STR:
        problems.append(f'{fid}: 默认存储非法 -> {default}')
    else:
        idx = {'room': 0, 'fridge': 1, 'frozen': 2}[default]
        if days[idx] == 'null':
            problems.append(f'{fid}: 默认存储 {default} 但没有天数')

    items.append((fid, name, cat, re.findall(r"'([^']*)'", args[3])))

py_block = src[src.index('const PINYIN = {'):]
py_block = py_block[:py_block.index('\n};')]
pinyin = dict(re.findall(r"'([^'])':'([^']*)'", py_block))

chars = set()
for _, name, _, aliases in items:
    for s in [name] + aliases:
        chars |= {c for c in s if not c.isascii()}
missing = sorted(c for c in chars if c not in pinyin)

ids = [i[0] for i in items]
dupes = sorted({i for i in ids if ids.count(i) > 1})

cats = {}
for i in items:
    cats[i[2]] = cats.get(i[2], 0) + 1

print('食材数:', len(items))
print('分类:', json.dumps(cats, ensure_ascii=False))
print('重复 id:', dupes if dupes else '无')
print('缺拼音字 (%d):' % len(missing), ''.join(missing) or '无')
print('参数问题:', '\n  '.join(problems) if problems else '无')

# ---- 引用校验：所有映射表里提到的 id 必须真实存在 ----
idset = {i[0] for i in items}
ghost = []


def need(mid):
    if mid not in idset:
        ghost.append(mid)


for name, tail in [('COOK_FOODS', '};'), ('MOD_FOODS', '};'), ('FOOD_RISK', '};'), ('EXTRA_NOTE', '};')]:
    m = re.search(r'const ' + name + r' = \{(.*?)\n\};', src, re.S)
    if m:
        for k in re.findall(r'^\s*(\w+)\s*:', m.group(1), re.M):
            need(k)

for name in ['HANDLE_FOODS']:
    m = re.search(r'const ' + name + r' = \[(.*?)\];', src, re.S)
    if m:
        for k in re.findall(r"'([\w]+)'", m.group(1)):
            need(k)

m = re.search(r'const REGION_FOODS = \{(.*?)\n\};', src, re.S)
if m:
    for k in re.findall(r"'([\w]+)'", m.group(1)):
        if k.isascii():
            need(k)

print('引用了不存在的 id:', sorted(set(ghost)) if ghost else '无')

# ---- 分类兜底校验：每条都必须能归到某个大类 ----
try:
    seg = src[src.index('const TOP_CLASS = {'):]
    seg = seg[:seg.index('\n};')]
    top_keys = set(re.findall(r'(\S+?):\s*\[', seg))

    seg = src[src.index('const DRY_ROUTE = {'):]
    seg = seg[:seg.index('\n};')]
    dry_keys = set(re.findall(r'(\w+)\s*:', seg))
except ValueError:
    top_keys, dry_keys = set(), set()

orphans = []
for fid, name, cat, _alias in items:
    if fid in dry_keys:
        continue
    if cat not in top_keys:
        orphans.append(f'{name}({fid}) 分类「{cat}」没有对应的大类')

print('归类兜底到「其他」的:', '\n  '.join(orphans) if orphans else '无')


