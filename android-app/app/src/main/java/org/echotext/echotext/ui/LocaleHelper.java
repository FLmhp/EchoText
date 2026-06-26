package org.echotext.echotext.ui;

import android.content.Context;
import android.content.res.Configuration;
import android.os.LocaleList;

import java.util.Locale;

public final class LocaleHelper {
    private LocaleHelper() {}

    public static Context wrap(Context context, String preference) {
        if (preference == null || preference.trim().isEmpty() || "auto".equals(preference)) {
            return context;
        }
        Locale locale = switch (preference) {
            case "zh" -> Locale.SIMPLIFIED_CHINESE;
            case "en" -> Locale.ENGLISH;
            default -> null;
        };
        if (locale == null) {
            return context;
        }
        Locale.setDefault(locale);
        Configuration configuration = new Configuration(context.getResources().getConfiguration());
        configuration.setLocale(locale);
        configuration.setLocales(new LocaleList(locale));
        return context.createConfigurationContext(configuration);
    }
}
