package io.iaiso.audit;

import org.junit.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.Assert.*;

public class EventTest {

    private Event sample() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("pressure", 0.42);
        return new Event("exec-1", "engine.step", 1700000000.5, data);
    }

    @Test
    public void jsonHasStableKeyOrder() {
        String s = sample().toJson();
        int sv = s.indexOf("\"schema_version\"");
        int eid = s.indexOf("\"execution_id\"");
        int kind = s.indexOf("\"kind\"");
        int ts = s.indexOf("\"timestamp\"");
        int data = s.indexOf("\"data\"");
        assertTrue(sv >= 0 && sv < eid);
        assertTrue(eid < kind);
        assertTrue(kind < ts);
        assertTrue(ts < data);
    }

    @Test
    public void schemaVersionDefault() {
        assertEquals(Event.SCHEMA_VERSION, sample().getSchemaVersion());
    }

    @Test
    public void memorySinkRecordsAndClears() {
        MemorySink s = new MemorySink();
        for (int i = 0; i < 3; i++) {
            s.emit(sample());
        }
        assertEquals(3, s.events().size());
        s.clear();
        assertEquals(0, s.events().size());
    }

    @Test
    public void nullSinkSwallows() {
        NullSink.INSTANCE.emit(sample()); // no exception
    }

    @Test
    public void fanoutBroadcasts() {
        MemorySink a = new MemorySink();
        MemorySink b = new MemorySink();
        Sink fan = new FanoutSink(a, b);
        fan.emit(sample());
        assertEquals(1, a.events().size());
        assertEquals(1, b.events().size());
    }

    @Test
    public void integerTimestampSerializesWithoutDecimal() {
        Map<String, Object> data = new LinkedHashMap<>();
        Event e = new Event("e", "k", 0.0, data);
        // Integer timestamps come out as "0", not "0.0"
        assertTrue(e.toJson().contains("\"timestamp\":0,"));
    }
}
