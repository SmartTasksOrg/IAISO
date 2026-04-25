import { describe, expect, it } from "vitest";

import { MemorySink } from "../src/audit/sinks/memory.js";
import {
  BoundedExecution,
  ExecutionLocked,
  ScopeRequired,
} from "../src/core/execution.js";
import { PressureConfig } from "../src/core/engine.js";
import { Lifecycle, StepOutcome } from "../src/core/types.js";
import { ConsentIssuer, InsufficientScope } from "../src/consent/index.js";

const KEY = "test_key_abcdefg01234567890";

describe("BoundedExecution.run (callback pattern)", () => {
  it("runs a successful block and emits execution.closed", async () => {
    const sink = new MemorySink();
    const result = await BoundedExecution.run(
      { audit_sink: sink, config: new PressureConfig() },
      async (exec) => {
        const outcome = exec.recordToolCall({ name: "search" });
        expect(outcome).toBe(StepOutcome.OK);
        return 42;
      },
    );
    expect(result).toBe(42);
    const closedEvent = sink.events.find((e) => e.kind === "execution.closed");
    expect(closedEvent).toBeDefined();
    expect(closedEvent!.data["exception"]).toBeNull();
  });

  it("propagates errors and records exception name", async () => {
    const sink = new MemorySink();
    await expect(
      BoundedExecution.run({ audit_sink: sink }, async () => {
        throw new TypeError("boom");
      }),
    ).rejects.toThrow(/boom/);
    const closed = sink.events.find((e) => e.kind === "execution.closed")!;
    expect(closed.data["exception"]).toBe("TypeError");
  });

  it("throws ExecutionLocked when pressure locks", async () => {
    const sink = new MemorySink();
    await expect(
      BoundedExecution.run(
        {
          audit_sink: sink,
          config: new PressureConfig({
            escalation_threshold: 0.5,
            release_threshold: 0.75,
            dissipation_per_step: 0.0,
            depth_coefficient: 0.75,
          }),
        },
        async (exec) => {
          exec.recordStep({ depth: 1 }); // releases + locks
          exec.recordStep({ depth: 1 }); // should throw
        },
      ),
    ).rejects.toThrow(ExecutionLocked);
  });
});

describe("requireScope", () => {
  it("throws ScopeRequired when no consent attached", async () => {
    const sink = new MemorySink();
    await expect(
      BoundedExecution.run({ audit_sink: sink }, async (exec) => {
        exec.requireScope("tools.search");
      }),
    ).rejects.toThrow(ScopeRequired);
    expect(sink.events.some((e) => e.kind === "consent.missing")).toBe(true);
  });

  it("emits consent.granted for allowed scopes", async () => {
    const sink = new MemorySink();
    const issuer = new ConsentIssuer({ signing_key: KEY, algorithm: "HS256" });
    const consent = issuer.issue({
      subject: "u",
      scopes: ["tools"],
      ttl_seconds: 60,
    });
    await BoundedExecution.run(
      { audit_sink: sink, consent },
      async (exec) => {
        exec.requireScope("tools.search");
      },
    );
    const granted = sink.events.find((e) => e.kind === "consent.granted");
    expect(granted).toBeDefined();
    expect(granted!.data["requested"]).toBe("tools.search");
  });

  it("emits consent.denied and throws InsufficientScope", async () => {
    const sink = new MemorySink();
    const issuer = new ConsentIssuer({ signing_key: KEY, algorithm: "HS256" });
    const consent = issuer.issue({
      subject: "u",
      scopes: ["tools.read"],
      ttl_seconds: 60,
    });
    await expect(
      BoundedExecution.run({ audit_sink: sink, consent }, async (exec) => {
        exec.requireScope("admin");
      }),
    ).rejects.toThrow(InsufficientScope);
    expect(sink.events.some((e) => e.kind === "consent.denied")).toBe(true);
  });
});

describe("check()", () => {
  it("returns OK before any steps", () => {
    const exec = BoundedExecution.start({ audit_sink: new MemorySink() });
    expect(exec.check()).toBe(StepOutcome.OK);
    exec.close();
  });

  it("returns ESCALATED when engine is escalated", () => {
    const exec = BoundedExecution.start({
      audit_sink: new MemorySink(),
      config: new PressureConfig({
        escalation_threshold: 0.5,
        release_threshold: 0.9,
        dissipation_per_step: 0.0,
        depth_coefficient: 0.5,
      }),
    });
    exec.recordStep({ depth: 1 });
    expect(exec.engine.lifecycle).toBe(Lifecycle.Escalated);
    expect(exec.check()).toBe(StepOutcome.Escalated);
    exec.close();
  });
});
