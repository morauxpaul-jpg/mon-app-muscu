package com.muscutracker.fit;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.appopen.AppOpenAd;

/**
 * Pub « App Open » (plein écran) affichée au RETOUR au premier plan de l'app.
 *
 * Choix volontaires :
 * - Pas d'affichage au démarrage à froid (l'annonce n'est pas prête à temps et
 *   c'est plus propre) : on n'affiche qu'au retour depuis l'arrière-plan.
 * - Plafonné à 1 affichage / 4 h, et on ignore les allers-retours < 30 s.
 * - L'identifiant de bloc est dans res/values/strings.xml (admob_app_open_id),
 *   actuellement l'ID de TEST Google.
 *
 * Limite connue : cette couche native ne connaît pas le statut VIP (il vit dans
 * la WebView). Le gating VIP sera branché en même temps que Google Play Billing.
 */
public class MainApplication extends Application
        implements Application.ActivityLifecycleCallbacks {

    private static final long SHOW_INTERVAL_MS = 4 * 60 * 60 * 1000L; // 1 / 4 h max
    private static final long MIN_BACKGROUND_MS = 30 * 1000L;         // ignore < 30 s

    private AppOpenAd appOpenAd = null;
    private boolean isLoadingAd = false;
    private boolean isShowingAd = false;

    private Activity currentActivity = null;
    private long lastShownAt = 0L;
    private long backgroundedAt = 0L;
    private boolean wasInBackground = false;

    @Override
    public void onCreate() {
        super.onCreate();
        registerActivityLifecycleCallbacks(this);
        MobileAds.initialize(this, status -> {});
        loadAd();
    }

    private boolean isAdAvailable() {
        return appOpenAd != null;
    }

    private void loadAd() {
        if (isLoadingAd || isAdAvailable()) {
            return;
        }
        isLoadingAd = true;
        AdRequest request = new AdRequest.Builder().build();
        AppOpenAd.load(
                this,
                getString(R.string.admob_app_open_id),
                request,
                new AppOpenAd.AppOpenAdLoadCallback() {
                    @Override
                    public void onAdLoaded(@NonNull AppOpenAd ad) {
                        appOpenAd = ad;
                        isLoadingAd = false;
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        isLoadingAd = false;
                    }
                });
    }

    private void showAdIfAvailable() {
        if (isShowingAd) {
            return;
        }
        if (System.currentTimeMillis() - lastShownAt < SHOW_INTERVAL_MS) {
            return;
        }
        if (!isAdAvailable() || currentActivity == null) {
            loadAd();
            return;
        }

        appOpenAd.setFullScreenContentCallback(new FullScreenContentCallback() {
            @Override
            public void onAdShowedFullScreenContent() {
                isShowingAd = true;
                lastShownAt = System.currentTimeMillis();
            }

            @Override
            public void onAdDismissedFullScreenContent() {
                appOpenAd = null;
                isShowingAd = false;
                loadAd(); // précharge la suivante
            }

            @Override
            public void onAdFailedToShowFullScreenContent(@NonNull AdError error) {
                appOpenAd = null;
                isShowingAd = false;
                loadAd();
            }
        });
        appOpenAd.show(currentActivity);
    }

    // ── Application.ActivityLifecycleCallbacks ───────────────────────
    @Override
    public void onActivityResumed(@NonNull Activity activity) {
        currentActivity = activity;
        if (wasInBackground) {
            wasInBackground = false;
            if (System.currentTimeMillis() - backgroundedAt >= MIN_BACKGROUND_MS) {
                showAdIfAvailable();
            }
        }
    }

    @Override
    public void onActivityStopped(@NonNull Activity activity) {
        // L'app passe en arrière-plan (sauf si c'est l'annonce plein écran qui
        // s'affiche par-dessus l'activité).
        if (!isShowingAd) {
            wasInBackground = true;
            backgroundedAt = System.currentTimeMillis();
        }
    }

    @Override
    public void onActivityStarted(@NonNull Activity activity) {
        if (!isShowingAd) {
            currentActivity = activity;
        }
    }

    @Override
    public void onActivityCreated(@NonNull Activity activity, @Nullable Bundle savedInstanceState) {
    }

    @Override
    public void onActivityPaused(@NonNull Activity activity) {
    }

    @Override
    public void onActivitySaveInstanceState(@NonNull Activity activity, @NonNull Bundle outState) {
    }

    @Override
    public void onActivityDestroyed(@NonNull Activity activity) {
    }
}
