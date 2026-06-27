package org.echotext.echotext.core;

import java.io.IOException;

public class TransportFailure extends IOException {
    public enum Kind {
        CONNECTION_REFUSED,
        CONNECTION_TIMEOUT,
        HOST_UNREACHABLE,
        PAIR_CODE_REJECTED,
        PEER_NOT_PAIRED,
        SIGNATURE_REJECTED,
        HTTP_FAILURE,
        GENERIC_IO
    }

    public final Kind kind;
    public final int statusCode;
    public final String detail;

    public TransportFailure(Kind kind, String detail) {
        this(kind, detail, 0, null);
    }

    public TransportFailure(Kind kind, String detail, Throwable cause) {
        this(kind, detail, 0, cause);
    }

    public TransportFailure(Kind kind, String detail, int statusCode, Throwable cause) {
        super(detail, cause);
        this.kind = kind;
        this.statusCode = statusCode;
        this.detail = detail;
    }

    public TransportFailure withDetail(String newDetail) {
        return new TransportFailure(kind, newDetail, statusCode, getCause());
    }
}
