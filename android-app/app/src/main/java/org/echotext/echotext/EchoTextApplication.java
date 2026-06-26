package org.echotext.echotext;

import android.app.Application;

import org.echotext.echotext.core.EchoTextController;

public class EchoTextApplication extends Application {
    private EchoTextController controller;

    @Override
    public void onCreate() {
        super.onCreate();
        controller = new EchoTextController(this);
    }

    public EchoTextController getController() {
        return controller;
    }
}
