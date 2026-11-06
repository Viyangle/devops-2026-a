"""E7 新增判定测试：错误集合多一条、finding 缺证据锚点时，evaluate 必须拒绝。

输入均为独立构造的小报告字典，不启动 Docker，也不改动参考实现的 EXPECTED 集合。
"""
import importlib.util
from pathlib import Path
import unittest

gate_path = next(parent / "scripts/run_e7_a_gate.py" for parent in Path(__file__).resolve().parents
                 if (parent / "scripts/run_e7_a_gate.py").is_file())
spec = importlib.util.spec_from_file_location("gate_rejections", gate_path)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def successful(findings):
    return {"trace_id": "test-extra", "status": "SUCCEEDED", "build_exit_code": 0, "clean_exit_code": 0, "findings": findings}


def anchored():
    return [{"type": kind, "target": target, "dependency": dependency, "evidence": ["trace/t.13:7"]}
            for kind, target, dependency in gate.EXPECTED]


class RejectionTests(unittest.TestCase):
    def test_extra_finding_and_missing_evidence_are_rejected(self):
        # 基线：与 EXPECTED 完全一致的集合必须通过，否则下面的拒绝断言没有意义
        gate.evaluate("original-2", 1, successful(anchored()))

        # 多出一条 finding：数量和集合都与 EXPECTED 不符，必须拒绝
        extra = anchored() + [{"type": "MISSING", "target": "main.o", "dependency": "stdio.h",
                               "evidence": ["trace/t.13:11"]}]
        with self.assertRaises(ValueError):
            gate.evaluate("original-2", 1, successful(extra))

        # 集合一致但缺证据锚点：CLI 仍退出 1，也必须拒绝
        without_evidence = anchored()
        without_evidence[0]["evidence"] = []
        with self.assertRaises(ValueError):
            gate.evaluate("original-2", 1, successful(without_evidence))


if __name__ == "__main__":
    unittest.main()
