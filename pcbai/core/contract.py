class PcbAiError(Exception):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.details = details


def result(summary, *, changed=False, verified="not_run", target=None, warnings=None, **extra):
    return dict(ok=True, changed=changed, verified=verified, summary=summary,
                measurements=[], warnings=list(warnings or []), target=target, **extra)


def error(exc):
    return dict(ok=False, changed=False, verified="not_run", summary=str(exc),
                error={"code": getattr(exc, "code", "internal_error"),
                       **({"details": exc.details} if getattr(exc, "details", None) is not None else {})},
                measurements=[], warnings=[])
