package com.muscutracker.fit;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

/**
 * Compte à rebours VIVANT dans la barre de notification, comme le minuteur de
 * l'application Horloge : le chiffre défile même app fermée.
 *
 * Aucun service en premier plan. C'est le SYSTÈME qui anime le compteur —
 * setUsesChronometer + setChronometerCountDown + une échéance ABSOLUE dans
 * setWhen(). Rien de notre code ne tourne pendant le repos, donc :
 *   • le compteur reste juste même si Android tue le processus de l'app ;
 *   • aucune consommation de batterie pendant les 90 secondes ;
 *   • pas de type de service à déclarer ni à justifier auprès de Google Play.
 *
 * Le bip de fin reste planifié séparément (Capacitor Local Notifications) :
 * cette notification-ci ne fait pas de bruit, elle affiche.
 */
final class RestTimerNotification {

    static final String CHANNEL_ID = "rest_timer";
    /** 4242 est déjà pris par la notification de FIN de repos (plugin). */
    static final int NOTIF_ID = 4243;

    private RestTimerNotification() {
    }

    private static void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        if (nm == null || nm.getNotificationChannel(CHANNEL_ID) != null) {
            return;
        }
        // IMPORTANCE_LOW : présent dans la barre, jamais de bandeau ni de son.
        // Le repos ne doit pas interrompre, il doit être consultable d'un
        // coup d'œil — l'alerte, elle, arrive à la fin.
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "Chrono de repos", NotificationManager.IMPORTANCE_LOW);
        ch.setDescription("Compte à rebours affiché pendant le repos entre deux séries.");
        ch.setShowBadge(false);
        ch.setSound(null, null);
        ch.enableVibration(false);
        nm.createNotificationChannel(ch);
    }

    /**
     * @param endAtMillis échéance absolue (epoch ms) — pas une durée : c'est
     *                    ce qui rend le compteur juste après une mise en
     *                    veille ou un redémarrage du processus.
     * @param exercice    nom affiché en seconde ligne, peut être vide.
     */
    static void show(Context ctx, long endAtMillis, String exercice) {
        if (endAtMillis <= System.currentTimeMillis()) {
            hide(ctx);
            return;
        }
        ensureChannel(ctx);

        Intent open = new Intent(ctx, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent tap = PendingIntent.getActivity(
                ctx, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_timer)
                .setContentTitle("Repos en cours")
                .setContentText(exercice == null || exercice.trim().isEmpty()
                        ? "Série suivante bientôt" : exercice.trim())
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setCategory(NotificationCompat.CATEGORY_STOPWATCH)
                .setOngoing(true)          // on ne balaie pas son chrono par erreur
                .setShowWhen(true)
                .setWhen(endAtMillis)
                .setUsesChronometer(true)
                // API 24+ ; en dessous, l'heure de fin s'affiche sans défiler.
                .setChronometerCountDown(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(tap);

        try {
            NotificationManagerCompat.from(ctx).notify(NOTIF_ID, b.build());
        } catch (SecurityException e) {
            // POST_NOTIFICATIONS refusée : on n'insiste pas, l'app garde son
            // propre chrono à l'écran.
        }
    }

    static void hide(Context ctx) {
        try {
            NotificationManagerCompat.from(ctx).cancel(NOTIF_ID);
        } catch (Exception e) {
            // rien à faire : au pire la notification disparaît à la fin
        }
    }
}
