package de.sljournal.android.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class Session(val server: String, val token: String, val device: String)

/**
 * Hält Serveradresse und Gerätetoken. Das Token liegt nur verschlüsselt in den
 * App-Einstellungen; der Schlüssel bleibt im Android-Keystore und verlässt das
 * Gerät nicht (auch nicht per Backup, siehe allowBackup=false im Manifest).
 */
class SessionStore(context: Context) {
    private val prefs = context.getSharedPreferences("session", Context.MODE_PRIVATE)

    fun load(): Session? {
        val server = prefs.getString(KEY_SERVER, null) ?: return null
        val encrypted = prefs.getString(KEY_TOKEN, null) ?: return null
        val token = runCatching { decrypt(encrypted) }.getOrNull() ?: return null
        return Session(server, token, prefs.getString(KEY_DEVICE, "") ?: "")
    }

    /** Zuletzt verwendete Adresse, damit sie nach dem Abmelden vorausgefüllt ist. */
    fun lastServer(): String = prefs.getString(KEY_SERVER, "") ?: ""

    fun save(session: Session) {
        prefs.edit()
            .putString(KEY_SERVER, session.server)
            .putString(KEY_TOKEN, encrypt(session.token))
            .putString(KEY_DEVICE, session.device)
            .apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_DEVICE).apply()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    private fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val data = cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(data, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): String {
        val data = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, data, 0, IV_LENGTH))
        return String(cipher.doFinal(data, IV_LENGTH, data.size - IV_LENGTH), Charsets.UTF_8)
    }

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val ALIAS = "sl-journal-session"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_LENGTH = 12
        const val KEY_SERVER = "server"
        const val KEY_TOKEN = "token"
        const val KEY_DEVICE = "device"
    }
}
