package io.iaiso.conformance;

import java.util.ArrayList;
import java.util.List;

/** Result of running one vector. */
public final class VectorResult {
    public final String section;
    public final String name;
    public final boolean passed;
    public final String message;

    public VectorResult(String section, String name, boolean passed, String message) {
        this.section = section;
        this.name = name;
        this.passed = passed;
        this.message = message;
    }

    public static VectorResult pass(String section, String name) {
        return new VectorResult(section, name, true, "");
    }

    public static VectorResult fail(String section, String name, String message) {
        return new VectorResult(section, name, false, message);
    }
}
