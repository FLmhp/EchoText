package org.echotext.echotext.core;

import androidx.annotation.StringRes;

import java.io.IOException;
import java.util.Locale;

import org.echotext.echotext.R;
import org.echotext.echotext.model.Peer;

public final class FailureStatusMapper {
    private FailureStatusMapper() {}

    @StringRes
    public static int stringResFor(Exception exception, Peer peer) {
        if (exception instanceof TransportFailure failure) {
            if (isWindowsPeer(peer) && isReachabilityFailure(failure.kind)) {
                return R.string.status_windows_lan_access;
            }
            return switch (failure.kind) {
                case CONNECTION_REFUSED -> R.string.status_connection_refused;
                case CONNECTION_TIMEOUT -> R.string.status_connection_timeout;
                case HOST_UNREACHABLE -> R.string.status_host_unreachable;
                case PAIR_CODE_REJECTED -> R.string.status_pair_code_rejected;
                case PEER_NOT_PAIRED -> R.string.status_pair_required;
                case SIGNATURE_REJECTED -> R.string.status_signature_rejected;
                case HTTP_FAILURE, GENERIC_IO -> R.string.status_request_failed;
            };
        }
        if (exception instanceof IOException && exception.getMessage() != null
                && exception.getMessage().contains("Pair with the device before sending text")) {
            return R.string.status_pair_required;
        }
        return R.string.status_request_failed;
    }

    private static boolean isWindowsPeer(Peer peer) {
        return peer != null && peer.platform.toLowerCase(Locale.ROOT).contains("windows");
    }

    private static boolean isReachabilityFailure(TransportFailure.Kind kind) {
        return kind == TransportFailure.Kind.CONNECTION_REFUSED
                || kind == TransportFailure.Kind.CONNECTION_TIMEOUT
                || kind == TransportFailure.Kind.HOST_UNREACHABLE;
    }
}
