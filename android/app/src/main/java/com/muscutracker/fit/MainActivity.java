package com.muscutracker.fit;

import android.app.DownloadManager;
import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.URLUtil;
import android.webkit.WebView;
import android.widget.Toast;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = null;
        try {
            if (this.getBridge() != null) {
                webView = this.getBridge().getWebView();
            }
        } catch (Exception e) {
            webView = null;
        }
        if (webView == null) return;

        // ── Export : le WebView ne gère pas nativement les téléchargements de
        // fichiers (Content-Disposition: attachment). On les prend en charge
        // via DownloadManager, en repassant le cookie de session pour rester
        // authentifié. Sans ça, « Exporter mon programme » ne faisait rien. ──
        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) {
                    request.addRequestHeader("Cookie", cookies);
                }
                if (userAgent != null) {
                    request.addRequestHeader("User-Agent", userAgent);
                }
                String fileName = URLUtil.guessFileName(url, contentDisposition, mimeType);
                request.setMimeType(mimeType);
                request.setTitle(fileName);
                request.setDescription("Muscu Tracker");
                request.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(
                        Environment.DIRECTORY_DOWNLOADS, fileName);
                request.allowScanningByMediaScanner();

                DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                if (dm != null) {
                    dm.enqueue(request);
                    Toast.makeText(getApplicationContext(),
                            "Téléchargement dans « Téléchargements »…",
                            Toast.LENGTH_SHORT).show();
                }
            } catch (Exception e) {
                Toast.makeText(getApplicationContext(),
                        "Échec du téléchargement", Toast.LENGTH_SHORT).show();
            }
        });

        // ── Chrono : pont pour baisser la musique de fond (Spotify…) pendant
        // l'alerte de fin de repos. Appelé depuis rest-timer.js via
        // window.MTAudio.duckAudio(ms). ──
        webView.addJavascriptInterface(new AudioBridge(this), "MTAudio");
    }

    /** Baisse temporairement la musique des autres apps (audio focus). */
    public static class AudioBridge {
        private final Handler handler = new Handler(Looper.getMainLooper());
        private final AudioManager am;
        private AudioFocusRequest focusRequest;

        AudioBridge(Context context) {
            this.am = (AudioManager) context.getApplicationContext()
                    .getSystemService(Context.AUDIO_SERVICE);
        }

        @JavascriptInterface
        public void duckAudio(final int ms) {
            handler.post(() -> {
                try {
                    if (am == null) return;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        AudioAttributes attrs = new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                                .build();
                        focusRequest = new AudioFocusRequest.Builder(
                                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                                .setAudioAttributes(attrs)
                                .build();
                        am.requestAudioFocus(focusRequest);
                    } else {
                        am.requestAudioFocus(null, AudioManager.STREAM_MUSIC,
                                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK);
                    }
                    int hold = Math.max(200, ms);
                    handler.postDelayed(this::abandonFocus, hold);
                } catch (Exception e) {
                    // silencieux : le ducking est un confort, jamais bloquant
                }
            });
        }

        private void abandonFocus() {
            try {
                if (am == null) return;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    if (focusRequest != null) {
                        am.abandonAudioFocusRequest(focusRequest);
                        focusRequest = null;
                    }
                } else {
                    am.abandonAudioFocus(null);
                }
            } catch (Exception e) {
                // no-op
            }
        }
    }
}
