package io.iaiso.conformance;

import org.junit.Test;

import java.nio.file.Path;
import java.nio.file.Paths;

import static org.junit.Assert.*;

public class ConformanceSuiteTest {

    private static Path specRoot() {
        // The build script and `mvn test` both run from the repo root,
        // so this resolves the same way in both. Fall back to project-local
        // spec if the property is absent.
        String prop = System.getProperty("iaiso.spec.dir");
        if (prop != null) return Paths.get(prop);
        // Try: <repo-root>/spec — that's where the spec lives in our layout.
        Path local = Paths.get("..", "spec");
        if (java.nio.file.Files.exists(local)) return local;
        return Paths.get("spec");
    }

    @Test
    public void allVectorsPass() throws Exception {
        SectionResults r = ConformanceRunner.runAll(specRoot());
        StringBuilder failures = new StringBuilder();
        for (java.util.List<VectorResult> bucket : new java.util.List[]{
                r.pressure, r.consent, r.events, r.policy}) {
            for (VectorResult v : bucket) {
                if (!v.passed) {
                    failures.append("\n  [").append(v.section).append("] ")
                        .append(v.name).append(": ").append(v.message);
                }
            }
        }
        int passed = r.countPassed();
        int total = r.countTotal();
        if (failures.length() > 0) {
            fail("conformance " + passed + "/" + total + " — failures:" + failures);
        }
        assertEquals("expected 67 total vectors", 67, total);
    }
}
