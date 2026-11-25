"""Independent checks for the native direct-binary SDS target adapter."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e8e10"))
from lab import commit, fixture, patch, run, scan, validate
from sds import BUILD_TARGET, COMPILER_FLAGS, EXPECTED_OUTPUT, HEADER, TARGETS


class SdsProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "sds"
        self.project.mkdir()
        (self.project / "sds.c").write_text(
            '#include <stdio.h>\n#include "sds.h"\n#include "sdsalloc.h"\n'
            '#ifdef SDS_TEST_MAIN\n#include "testhelp.h"\n'
            'int main(void){puts(TEST_SUMMARY);return 0;}\n#endif\n'
        )
        (self.project / "sds.h").write_text("#define SDS_VALUE 1\n")
        (self.project / "sdsalloc.h").write_text("#define SDS_ALLOC 1\n")
        (self.project / "testhelp.h").write_text('#define TEST_SUMMARY "' + EXPECTED_OUTPUT + '"\n')
        (self.project / "Makefile").write_text(
            "all: sds-test\nsds-test: sds.c sds.h testhelp.h\n"
            "\tgcc -o sds-test sds.c -Wall -std=c99 -pedantic -O2 -DSDS_TEST_MAIN\n"
            "clean:\n\trm -f sds-test\n"
        )
        run(["git", "init", "-b", "main"], self.project)
        run(["git", "config", "user.name", "SdsAdapterTest"], self.project)
        run(["git", "config", "user.email", "test@localhost"], self.project)
        commit(self.project, "native direct-binary input")

    def scan_sds(self, old=None):
        return scan(self.project, old, targets=TARGETS, compiler_flags=COMPILER_FLAGS)

    def test_native_binary_target_observes_conditional_test_header(self):
        report = self.scan_sds()
        self.assertEqual(report["actual"], {BUILD_TARGET: ["sds.c", "sds.h", "sdsalloc.h", "testhelp.h"]})
        self.assertEqual(report["findings"], [{"type": "MISSING", "target": BUILD_TARGET, "dependency": HEADER}])
        self.assertEqual(report["refreshed"], [BUILD_TARGET])

    def test_declaration_only_upstream_fix_reuses_actual_graph(self):
        previous = self.scan_sds()
        makefile = self.project / "Makefile"
        makefile.write_text(makefile.read_text().replace("sds.c sds.h testhelp.h", "sds.c sds.h testhelp.h sdsalloc.h"))
        commit(self.project, "declare allocator header")
        current = self.scan_sds(previous)
        self.assertEqual(current["findings"], [])
        self.assertEqual(current["reused"], [BUILD_TARGET])
        self.assertEqual(current["refreshed"], [])
        self.assertEqual(current["resolved"], [["MISSING", BUILD_TARGET, HEADER]])

    def test_patch_validates_real_header_rebuild_and_keeps_native_rule(self):
        difference, edits = patch(self.project, self.scan_sds())
        self.assertEqual(edits, [{"target": BUILD_TARGET, "dependency": HEADER, "style": "direct"}])
        self.assertIn("+sds-test: sds.c sds.h testhelp.h sdsalloc.h", difference)
        patchfile = self.root / "candidate.patch"
        patchfile.write_text(difference)
        result = validate(
            self.project, patchfile, self.root / "validation", targets=TARGETS,
            compiler_flags=COMPILER_FLAGS, build_target=BUILD_TARGET,
            expected_output=EXPECTED_OUTPUT, rebuild_header=HEADER,
        )
        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["checks"]["header_change"])
        self.assertTrue(result["checks"]["header_test"])
        self.assertEqual((self.root / "validation/test.log").read_text().strip(), EXPECTED_OUTPUT)
        self.assertEqual(json.loads((self.root / "validation/recheck.json").read_text())["findings"], [])

    def test_course_default_scan_and_validation_still_work(self):
        project = self.root / "course"
        fixture(project)
        report = scan(project)
        self.assertEqual(report["key"]["flags"], "-O0")
        self.assertNotIn("targets", report["key"])
        self.assertEqual(report["actual"]["main.o"], ["config.h", "main.c"])
        difference, _ = patch(project, report)
        patchfile = self.root / "course.patch"
        patchfile.write_text(difference)
        result = validate(project, patchfile, self.root / "course-validation")
        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["checks"]["header_change"])


if __name__ == "__main__":
    unittest.main()
