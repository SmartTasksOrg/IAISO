using System;

namespace Iaiso.Middleware;

/// <summary>Base type for middleware-induced failures.</summary>
public abstract class MiddlewareException : Exception
{
    protected MiddlewareException(string message) : base(message) {}
    protected MiddlewareException(string message, Exception inner) : base(message, inner) {}

    /// <summary>Raised when <c>RaiseOnEscalation</c> is true and the engine has escalated.</summary>
    public sealed class EscalationRaised : MiddlewareException
    {
        public EscalationRaised() : base("execution escalated; raise-on-escalation enabled") {}
    }

    /// <summary>Raised when the execution is locked.</summary>
    public sealed class Locked : MiddlewareException
    {
        public Locked() : base("execution locked") {}
    }

    /// <summary>Raised when the upstream provider call failed.</summary>
    public sealed class Provider : MiddlewareException
    {
        public Provider(string message) : base("provider error: " + message) {}
        public Provider(string message, Exception inner)
            : base("provider error: " + message, inner) {}
    }
}
