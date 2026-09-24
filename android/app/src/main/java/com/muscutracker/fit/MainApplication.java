package com.muscutracker.fit;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;
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
 * - L'identifiant de bloc est dans res/values/strings.xml (admob_app_open_id) :
 *   c'est l'ID de PRODUCTION du compte AdMob, pas un ID de test.
 *
 * Statut PRO : la WebView le recopie dans les préférences via le pont
 * `window.MTAds.setTier(…)` (cf. MainActivity.AdsBridge). Tant qu'elle n'a
 * rien dit, aucune pub n'est chargée ni affichée : rater une impression coûte
 * moins cher que d'en imposer une à quelqu'un qui paie.
 */
public class MainApplication extends Application
        implements Application.ActivityLifecycleCallbacks {

    private static final long SHOW_INTERVAL_MS = 4 * 60 * 60 * 1000L; // 1 / 4 h max
    private static final long MIN_BACKGROUND_MS = 30 * 1000L;         // ignore < 30 s

    /** Partagé avec MainActivity.AdsBridge (écrit par la WebView). */
    static final String ADS_PREFS = "mt_ads";
    static final String KEY_NO_ADS = "no_ads";
    static final String KEY_TIER_AT = "tier_at";

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
        // Au démarrage à froid le statut n'est pas encore connu : loadAd() sort
        // aussitôt. Le préchargement repart au premier retour au premier plan,
        // quand la WebView a eu le temps de dire qui est l'utilisateur.
        loadAd();
    }

    private boolean isAdAvailable() {
        return appOpenAd != null;
    }

    /**
     * True s'il ne faut ni charger ni afficher de pub : membre PRO, ou statut
     * encore inconnu (première ouverture, avant le premier rendu de page).
     */
    private boolean adsDisabled() {
        try {
            SharedPreferences p = getSharedPreferences(ADS_PREFS, Context.MODE_PRIVATE);
            if (p.getLong(KEY_TIER_AT, 0L) == 0L) {
                return true; // la WebView n'a pas encore parlé
            }
            return p.getBoolean(KEY_NO_ADS, false);
        } catch (Exception e) {
            return true; // dans le doute, pas de pub
        }
    }

    private void loadAd() {
        if (isLoadingAd || isAdAvailable() || adsDisabled()) {
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
        if (isShowingAd || adsDisabled()) {
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
        loadAd(); // no-op tant que adsDisabled()
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
