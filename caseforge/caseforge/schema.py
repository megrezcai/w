"""Chapter format and cross-reference validation, shared by importer and runtime."""
import json
from pathlib import Path

S = lambda **kw: dict(type='string', **kw)
NUM = dict(type='number', minimum=0, maximum=10)
def obj(properties, required=None):
    return dict(type='object', properties=properties, required=required or list(properties), additionalProperties=False)
def arr(items, **kw):
    return dict(type='array', items=items, **kw)
ID = S(pattern=r'^[a-z][a-z0-9_]{0,47}$')
CHARACTER = obj({
    'id': ID, 'name': S(minLength=1), 'persona': S(minLength=1),
    'public_knowledge': arr(S()),
    'interests': arr(obj({'id': ID, 'label': S(), 'weight': NUM}), minItems=1, maxItems=8),
    'initial_trust': dict(type='number', minimum=0, maximum=1),
    'red_lines': arr(ID),
    'secrets': arr(obj({
        'id': ID, 'topic': S(minLength=1), 'hints': arr(S(minLength=1), minItems=1),
        'truth': S(minLength=1), 'denial': S(minLength=1), 'cost': NUM,
        'requires': arr(ID), 'evidence': arr(ID), 'requires_offers': arr(ID),
    }), minItems=1, maxItems=12),
})
CHAPTER_SCHEMA = obj({
    'version': dict(type='integer', const=1), 'id': ID, 'title': S(minLength=1),
    'public_brief': S(minLength=1),
    'evidence': arr(obj({
        'id': ID, 'title': S(minLength=1), 'description': S(minLength=1),
        'effects': arr(obj({'character': ID, 'leverage': NUM, 'betrayal': dict(type='number', minimum=0, maximum=1)})),
    }), maxItems=30),
    'offers': arr(obj({
        'id': ID, 'title': S(minLength=1), 'description': S(minLength=1),
        'benefits': arr(obj({'character': ID, 'interest': ID, 'value': dict(type='number', minimum=-1, maximum=1)})),
        'counter_line': S(minLength=1),
    }), maxItems=20),
    'characters': arr(CHARACTER, minItems=1, maxItems=8),
})

class ChapterError(ValueError):
    pass

def check_schema(value, schema, path='$'):
    """The restricted JSON Schema subset above, without third-party dependencies."""
    typ = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str),
             'number': type(value) in (int, float), 'integer': type(value) is int}
    if not valid.get(typ, True):
        raise ChapterError(f'{path}: 需要 {typ}')
    if 'const' in schema and value != schema['const']:
        raise ChapterError(f'{path}: 版本必须为 {schema["const"]}')
    if typ in ('number', 'integer'):
        import math
        if not math.isfinite(value) or not schema.get('minimum', -1e9) <= value <= schema.get('maximum', 1e9):
            raise ChapterError(f'{path}: 数值超出范围')
    if typ == 'string':
        import re
        if not schema.get('minLength', 0) <= len(value) <= 12000:
            raise ChapterError(f'{path}: 文本为空或过长')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'], value):
            raise ChapterError(f'{path}: id 只能使用小写字母、数字、下划线，且以字母开头')
    if typ == 'array':
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 100):
            raise ChapterError(f'{path}: 列表长度不合法')
        for i, item in enumerate(value):
            check_schema(item, schema['items'], f'{path}[{i}]')
    if typ == 'object':
        missing = set(schema.get('required', [])) - set(value)
        extra = set(value) - set(schema['properties'])
        if missing or extra:
            raise ChapterError(f'{path}: 缺少字段 {sorted(missing)}；未知字段 {sorted(extra)}')
        for k, v in value.items():
            check_schema(v, schema['properties'][k], f'{path}.{k}')

def validate(chapter):
    check_schema(chapter, CHAPTER_SCHEMA)
    def indexed(items, path):
        result = {i['id']: i for i in items}
        if len(result) != len(items):
            raise ChapterError(f'{path}: id 重复')
        return result
    chars = indexed(chapter['characters'], 'characters')
    evidence = indexed(chapter['evidence'], 'evidence')
    offers = indexed(chapter['offers'], 'offers')
    def refs(values, allowed, path):
        unknown = set(values) - set(allowed)
        if unknown:
            raise ChapterError(f'{path}: 引用不存在 {sorted(unknown)}')
    for c in chars.values():
        interests = indexed(c['interests'], c['id'] + '.interests')
        if not any(i['weight'] > 0 for i in interests.values()):
            raise ChapterError('至少一个利益权重必须大于零')
        refs(c['red_lines'], offers, 'red_lines')
        secrets = indexed(c['secrets'], c['id'] + '.secrets')
        for s in secrets.values():
            refs(s['requires'], secrets, 'requires')
            refs(s['evidence'], evidence, 'evidence')
            refs(s['requires_offers'], offers, 'requires_offers')
        visiting, done = set(), set()
        def visit(k):
            if k in visiting:
                raise ChapterError('秘密依赖包含循环')
            if k in done:
                return
            visiting.add(k)
            for dep in secrets[k]['requires']:
                visit(dep)
            visiting.remove(k)
            done.add(k)
        for k in secrets:
            visit(k)
    for e in evidence.values():
        for effect in e['effects']:
            refs([effect['character']], chars, 'evidence.character')
    for o in offers.values():
        for b in o['benefits']:
            refs([b['character']], chars, 'offers.character')
            refs([b['interest']], [i['id'] for i in chars[b['character']]['interests']], 'offers.interest')
    return chapter

def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8-sig')))
