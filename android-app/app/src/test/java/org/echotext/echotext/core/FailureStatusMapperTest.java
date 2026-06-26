package org.echotext.echotext.core;

import static org.junit.Assert.assertEquals;

import org.echotext.echotext.R;
import org.echotext.echotext.model.Peer;
import org.junit.Test;

public class FailureStatusMapperTest {
    @Test
    public void windowsReachabilityFailuresMapToLanAccessWarning() {
        Peer peer = new Peer("device", "Desktop", "Windows", "192.168.1.10", 9999, 0.0, null);

        int stringRes = FailureStatusMapper.stringResFor(
                new TransportFailure(TransportFailure.Kind.CONNECTION_REFUSED, "refused"),
                peer);

        assertEquals(R.string.status_windows_lan_access, stringRes);
    }

    @Test
    public void pairCodeRejectionsMapToSpecificStatus() {
        Peer peer = new Peer("device", "Phone", "Android", "192.168.1.20", 9999, 0.0, null);

        int stringRes = FailureStatusMapper.stringResFor(
                new TransportFailure(TransportFailure.Kind.PAIR_CODE_REJECTED, "pair_code_rejected"),
                peer);

        assertEquals(R.string.status_pair_code_rejected, stringRes);
    }

    @Test
    public void hostUnreachableMapsToStableStatus() {
        Peer peer = new Peer("device", "Phone", "Android", "192.168.1.20", 9999, 0.0, null);

        int stringRes = FailureStatusMapper.stringResFor(
                new TransportFailure(TransportFailure.Kind.HOST_UNREACHABLE, "unreachable"),
                peer);

        assertEquals(R.string.status_host_unreachable, stringRes);
    }
}
