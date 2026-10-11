package audit

import (
	"bytes"
	"context"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// HTTPDoer is the structural interface WebhookSink needs. *http.Client
// satisfies it. Keeping it structural means the SDK takes no dependency on
// any particular HTTP stack, and tests need no network.
type HTTPDoer interface {
	Do(req *http.Request) (*http.Response, error)
}

// WebhookOptions configures a WebhookSink.
type WebhookOptions struct {
	// URL receives a POST per event, body = the JSON envelope.
	URL string
	// Headers are attached to every request (e.g. Authorization).
	Headers map[string]string
	// QueueSize bounds the in-flight buffer. Default 1024.
	QueueSize int
	// Timeout per request. Default 5s.
	Timeout time.Duration
	// Client defaults to an *http.Client with Timeout.
	Client HTTPDoer
}

// WebhookSink POSTs each event to a URL from a background goroutine, with a
// bounded queue and drop-on-overflow.
//
// Delivery is BEST-EFFORT. When the queue is full, events are dropped and
// Dropped() increments. Export that counter as iaiso_sink_dropped_total and
// alert on it. If you cannot tolerate loss, use JSONLFileSink plus a
// shipper. See LIMITATIONS.md §4.2.
type WebhookSink struct {
	opts    WebhookOptions
	client  HTTPDoer
	queue   chan Event
	dropped atomic.Int64
	sent    atomic.Int64
	failed  atomic.Int64
	stop    chan struct{}
	wg      sync.WaitGroup
	once    sync.Once
}

// NewWebhookSink starts the delivery goroutine. Call Close to drain it.
func NewWebhookSink(opts WebhookOptions) *WebhookSink {
	if opts.QueueSize <= 0 {
		opts.QueueSize = 1024
	}
	if opts.Timeout <= 0 {
		opts.Timeout = 5 * time.Second
	}
	client := opts.Client
	if client == nil {
		client = &http.Client{Timeout: opts.Timeout}
	}
	s := &WebhookSink{
		opts:   opts,
		client: client,
		queue:  make(chan Event, opts.QueueSize),
		stop:   make(chan struct{}),
	}
	s.wg.Add(1)
	go s.loop()
	return s
}

// Emit implements Sink. It never blocks: a full queue drops the event.
func (s *WebhookSink) Emit(ev Event) {
	select {
	case s.queue <- ev:
	default:
		s.dropped.Add(1)
	}
}

// Dropped reports events discarded because the queue was full.
// This is the value behind the iaiso_sink_dropped_total metric.
func (s *WebhookSink) Dropped() int64 { return s.dropped.Load() }

// Sent reports events successfully delivered (2xx response).
func (s *WebhookSink) Sent() int64 { return s.sent.Load() }

// Failed reports events whose POST errored or returned non-2xx.
func (s *WebhookSink) Failed() int64 { return s.failed.Load() }

// Close drains the queue and stops the delivery goroutine. Idempotent.
func (s *WebhookSink) Close() {
	s.once.Do(func() {
		close(s.stop)
		s.wg.Wait()
	})
}

func (s *WebhookSink) loop() {
	defer s.wg.Done()
	for {
		select {
		case ev := <-s.queue:
			s.post(ev)
		case <-s.stop:
			for {
				select {
				case ev := <-s.queue:
					s.post(ev)
				default:
					return
				}
			}
		}
	}
}

func (s *WebhookSink) post(ev Event) {
	body, err := ev.JSON()
	if err != nil {
		s.failed.Add(1)
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), s.opts.Timeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.opts.URL, bytes.NewReader(body))
	if err != nil {
		s.failed.Add(1)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range s.opts.Headers {
		req.Header.Set(k, v)
	}
	resp, err := s.client.Do(req)
	if err != nil {
		s.failed.Add(1)
		return
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		s.failed.Add(1)
		return
	}
	s.sent.Add(1)
}
