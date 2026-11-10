package io.iaiso.conformance;

import java.io.IOException;
import java.nio.file.Path;

/** Top-level conformance runner. */
public final class ConformanceRunner {
    private ConformanceRunner() {}

    /** Run every section against the spec at {@code specRoot}. */
    public static SectionResults runAll(Path specRoot) throws IOException {
        SectionResults s = new SectionResults();
        s.pressure.addAll(PressureRunner.run(specRoot));
        s.consent.addAll(ConsentRunner.run(specRoot));
        s.events.addAll(EventsRunner.run(specRoot));
        s.policy.addAll(PolicyRunner.run(specRoot));
        return s;
    }
}
