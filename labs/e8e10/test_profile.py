import json, tempfile, unittest
from pathlib import Path
from lab import fixture,scan,patch,commit

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def test_independent_known_edges(self):
        r=scan(self.p)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in r['findings']},{('MISSING','config.h'),('REDUNDANT','unused.h')})

    def test_unchanged_reuses_both_targets(self):
        r=scan(self.p,scan(self.p));self.assertEqual(r['reused'],['main.o','helper.o']);self.assertEqual(r['refreshed'],[])

    def test_include_added_invalidates_cache(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "extra.h"\n'+(self.p/'main.c').read_text());commit(self.p,'new include')
        r=scan(self.p,old)
        self.assertIn(['MISSING','main.o','extra.h'],r['added']);self.assertEqual(len(r['refreshed']),2)

    def test_patch_preserves_redundant_dependency(self):
        r=scan(self.p);diff,plan=patch(self.p,r)
        self.assertIn('+main.o: main.c unused.h config.h',diff)
        self.assertNotIn('-\tgcc',diff)
        self.assertNotIn('config.h',(self.p/'Makefile').read_text())

    def test_old_report_rejected(self):
        r=scan(self.p);r['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'STALE_REPORT'):patch(self.p,r)

    def test_unsafe_dependency_rejected(self):
        r=scan(self.p);r['findings']=[{'type':'MISSING','target':'main.o','dependency':'../outside.h'}]
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):patch(self.p,r)

    def test_unsupported_configuration_rejected(self):
        (self.p/'Makefile').write_text((self.p/'Makefile').read_text().replace('-O0','-include unknown.h'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FLAGS'):scan(self.p)

class StudentE8A241250014(unittest.TestCase):
    """E8 A：先写独立预期，再验证“间接头文件变化”会让历史图失效。"""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'e8a';fixture(self.p)

    def test_indirect_header_change_invalidates_history(self):
        old=scan(self.p)
        # 独立预期：C0 实际读取 main.o<-{config.h,main.c}，声明缺 config.h、多 unused.h。
        self.assertEqual(old['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in old['findings']},
                         {('MISSING','config.h'),('REDUNDANT','unused.h')})
        # 只在 config.h 内部增加 include，不改 Makefile 声明。
        (self.p/'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        commit(self.p,'indirect include only inside config.h')
        r=scan(self.p,old);full=scan(self.p)
        # 独立预期：预处理结构变化使两个目标都刷新，实际图新增 extra.h，
        # 原来的 MISSING config.h 仍然存在（不因本次变化再次计入 added）。
        self.assertEqual(r['refreshed'],['main.o','helper.o'])
        self.assertEqual(r['reused'],[])
        self.assertEqual(r['actual']['main.o'],['config.h','extra.h','main.c'])
        self.assertIn(['MISSING','main.o','extra.h'],r['added'])
        self.assertNotIn(['MISSING','main.o','config.h'],r['added'])
        self.assertIn({'type':'MISSING','target':'main.o','dependency':'config.h'},r['findings'])
        self.assertEqual(r['actual'],full['actual'])
        self.assertEqual(r['findings'],full['findings'])


class StudentE9A241250014(unittest.TestCase):
    """E9 A：C1 复用、C2 刷新并新增、C3 只更新声明图并消除 MD，四步独立预期。"""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'e9a';fixture(self.p)

    def test_stepwise_c1_c2_c3_reports(self):
        p=self.p;baseline=scan(p)
        (p/'main.c').write_text((p/'main.c').read_text().replace('VALUE+helper()','VALUE+helper()+0'))
        c1=commit(p,'C1 body change');r1=scan(p,baseline)
        # 独立预期：普通函数体变化不改预处理/配方，两个目标复用且发现集合不变。
        self.assertEqual(r1['commit'],c1)
        self.assertEqual(r1['reused'],['main.o','helper.o'])
        self.assertEqual(r1['refreshed'],[])
        self.assertEqual(r1['findings'],baseline['findings'])
        (p/'main.c').write_text('#include "extra.h"\n'+(p/'main.c').read_text())
        commit(p,'C2 include change');r2=scan(p,r1)
        # 独立预期：新 include 使两个目标刷新，且只新增一条 MISSING extra.h。
        self.assertEqual(r2['refreshed'],['main.o','helper.o'])
        self.assertEqual(r2['added'],[['MISSING','main.o','extra.h']])
        self.assertIn({'type':'MISSING','target':'main.o','dependency':'config.h'},r2['findings'])
        (p/'Makefile').write_text((p/'Makefile').read_text().replace('main.c unused.h','main.c unused.h config.h extra.h'))
        commit(p,'C3 repair declarations');r3=scan(p,r2)
        # 独立预期：只改声明时实际图仍可复用；两条 MISSING 消除，REDUNDANT unused.h 保留。
        self.assertEqual(r3['reused'],['main.o','helper.o'])
        self.assertEqual(r3['resolved'],[['MISSING','main.o','config.h'],['MISSING','main.o','extra.h']])
        self.assertEqual(r3['findings'],[{'type':'REDUNDANT','target':'main.o','dependency':'unused.h'}])


class StudentE10A241250014(unittest.TestCase):
    """E10 A：新增“编译配置身份变化”场景，五次增/全量对照且预期逐次变化。"""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'e10a';fixture(self.p)

    def test_configuration_change_repeats_match_full_scan(self):
        p=self.p;previous=scan(p)
        (p/'Makefile').write_text((p/'Makefile').read_text().replace('CFLAGS = -O0','CFLAGS = -O0 -DMODE=1'))
        commit(p,'configuration identity change')
        rows=[]
        for repeat in range(1,6):
            inc=scan(p,previous);full=scan(p)
            # 独立预期：每次增量与全量的 actual/declared/findings 必须完全一致。
            self.assertEqual(inc['actual'],full['actual'])
            self.assertEqual(inc['declared'],full['declared'])
            self.assertEqual(inc['findings'],full['findings'])
            self.assertEqual(inc['findings'],[{'type':'MISSING','target':'main.o','dependency':'config.h'},
                                              {'type':'REDUNDANT','target':'main.o','dependency':'unused.h'}])
            # 独立预期：配置身份第一次变化时两个目标都刷新，之后同一配置下复用。
            if repeat==1:
                self.assertEqual(inc['refreshed'],['main.o','helper.o'])
                self.assertEqual(inc['reused'],[])
            else:
                self.assertEqual(inc['reused'],['main.o','helper.o'])
                self.assertEqual(inc['refreshed'],[])
            rows.append((repeat,tuple(inc['reused']),tuple(inc['refreshed'])))
            previous=inc
        self.assertEqual(len(rows),5)


class StudentE8A241250033(unittest.TestCase):
    """E8 A (241250033)：仅补齐声明时复用真实依赖图，消除 MISSING config.h 且保留 REDUNDANT unused.h。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / 'e8a-241250033'
        fixture(self.p)

    def test_declaration_only_change_reuses_actual_graph_and_resolves_md(self):
        old = scan(self.p)
        mf = self.p / 'Makefile'
        mf.write_text(mf.read_text().replace('main.c unused.h', 'main.c unused.h config.h'))
        commit(self.p, '241250033: add missing config.h declaration')
        result = scan(self.p, old)
        full = scan(self.p)
        self.assertEqual(result['actual'], old['actual'])
        self.assertEqual(result['reused'], ['main.o', 'helper.o'])
        self.assertEqual(result['refreshed'], [])
        self.assertEqual(result['resolved'], [['MISSING', 'main.o', 'config.h']])
        self.assertEqual(result['added'], [])
        self.assertEqual(result['findings'], [{'type': 'REDUNDANT', 'target': 'main.o', 'dependency': 'unused.h'}])
        self.assertEqual(result['actual'], full['actual'])
        self.assertEqual(result['declared'], full['declared'])
        self.assertEqual(result['findings'], full['findings'])


class StudentE9A241250033(unittest.TestCase):
    """E9 A (241250033)：头文件新增 include 触发刷新，随后移除并转移到 helper.c 验证消除与新增集合。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / 'e9a-241250033'
        fixture(self.p)

    def test_header_directive_addition_and_removal_across_commits(self):
        old = scan(self.p)
        (self.p / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        commit(self.p, '241250033: config.h includes extra.h')
        r1 = scan(self.p, old)
        full1 = scan(self.p)
        self.assertEqual(r1['refreshed'], ['main.o', 'helper.o'])
        self.assertEqual(r1['reused'], [])
        self.assertEqual(r1['actual']['main.o'], ['config.h', 'extra.h', 'main.c'])
        self.assertEqual(r1['added'], [['MISSING', 'main.o', 'extra.h']])
        self.assertEqual(r1['resolved'], [])
        self.assertEqual(r1['actual'], full1['actual'])
        self.assertEqual(r1['findings'], full1['findings'])

        (self.p / 'config.h').write_text('#define VALUE 1\n')
        (self.p / 'helper.c').write_text('#include "extra.h"\nint helper(void){return 0;}\n')
        commit(self.p, '241250033: move extra.h include from config.h to helper.c')
        r2 = scan(self.p, r1)
        full2 = scan(self.p)
        self.assertEqual(r2['refreshed'], ['main.o', 'helper.o'])
        self.assertEqual(r2['reused'], [])
        self.assertEqual(r2['actual']['main.o'], ['config.h', 'main.c'])
        self.assertEqual(r2['actual']['helper.o'], ['extra.h', 'helper.c'])
        self.assertEqual(r2['resolved'], [['MISSING', 'main.o', 'extra.h']])
        self.assertEqual(r2['added'], [['MISSING', 'helper.o', 'extra.h']])
        self.assertEqual(r2['actual'], full2['actual'])
        self.assertEqual(r2['declared'], full2['declared'])
        self.assertEqual(r2['findings'], full2['findings'])


class StudentE10A241250033(unittest.TestCase):
    """E10 A (241250033)：三层传递包含（config.h -> extra.h -> leaf.h）五次重复增量/全量一致性与复用。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name) / 'e10a-241250033'
        fixture(self.p)

    def test_transitive_include_five_repeats_consistency_and_reuse(self):
        previous = scan(self.p)
        (self.p / 'config.h').write_text('#include "extra.h"\n#define VALUE 1\n')
        (self.p / 'extra.h').write_text('#include "leaf.h"\n#define EXTRA 0\n')
        (self.p / 'leaf.h').write_text('#define LEAF 7\n')
        commit(self.p, '241250033: three-level transitive include')
        for repeat in range(1, 6):
            inc = scan(self.p, previous)
            full = scan(self.p)
            self.assertEqual(inc['actual'], full['actual'])
            self.assertEqual(inc['declared'], full['declared'])
            self.assertEqual(inc['findings'], full['findings'])
            self.assertEqual(inc['actual']['main.o'], ['config.h', 'extra.h', 'leaf.h', 'main.c'])
            missing = {x['dependency'] for x in inc['findings'] if x['type'] == 'MISSING'}
            self.assertEqual(missing, {'config.h', 'extra.h', 'leaf.h'})
            redundant = {x['dependency'] for x in inc['findings'] if x['type'] == 'REDUNDANT'}
            self.assertEqual(redundant, {'unused.h'})
            if repeat == 1:
                self.assertEqual(inc['refreshed'], ['main.o', 'helper.o'])
                self.assertEqual(inc['reused'], [])
                self.assertEqual(sorted(inc['added']), [['MISSING', 'main.o', 'extra.h'], ['MISSING', 'main.o', 'leaf.h']])
            else:
                self.assertEqual(inc['reused'], ['main.o', 'helper.o'])
                self.assertEqual(inc['refreshed'], [])
                self.assertEqual(inc['added'], [])
                self.assertEqual(inc['resolved'], [])
            previous = inc


if __name__=='__main__':unittest.main()
