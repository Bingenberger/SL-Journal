package de.sljournal.android.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/** Fehler mit einer Meldung, die direkt angezeigt werden kann. */
open class ApiException(message: String, val status: Int = 0) : Exception(message)

/** Das Gerätetoken gilt nicht mehr: erneut anmelden. */
class UnauthorizedException(message: String) : ApiException(message, 401)

val json = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    encodeDefaults = true
}

private val JSON_TYPE = "application/json; charset=utf-8".toMediaType()

private val http: OkHttpClient = OkHttpClient.Builder()
    .connectTimeout(15, TimeUnit.SECONDS)
    .readTimeout(60, TimeUnit.SECONDS)
    .writeTimeout(120, TimeUnit.SECONDS)
    // Kein Cookie-Speicher: Die App arbeitet ausschließlich mit dem Gerätetoken.
    .followRedirects(false)
    .build()

/**
 * Normalisiert die eingegebene Serveradresse. Erlaubt ist nur HTTPS; ein
 * fehlendes Schema wird ergänzt, ein abschließender Schrägstrich entfernt.
 */
fun normalizeServer(input: String): HttpUrl {
    var text = input.trim().trimEnd('/')
    if (text.isEmpty()) throw ApiException("Bitte die Adresse des Journals eingeben.")
    if (text.startsWith("http://", ignoreCase = true)) {
        throw ApiException("Das Journal ist nur über HTTPS erreichbar. Bitte die https://-Adresse verwenden.")
    }
    if (!text.startsWith("https://", ignoreCase = true)) text = "https://$text"
    return text.toHttpUrlOrNull() ?: throw ApiException("Die Adresse ist ungültig.")
}

class JournalApi(private val server: HttpUrl, private val token: String?) {

    private fun url(path: String, query: Map<String, String?> = emptyMap()): HttpUrl {
        val builder = server.newBuilder()
        path.trim('/').split('/').forEach { builder.addPathSegment(it) }
        query.forEach { (k, v) -> if (!v.isNullOrEmpty()) builder.addQueryParameter(k, v) }
        return builder.build()
    }

    private suspend fun call(method: String, path: String, query: Map<String, String?> = emptyMap(), body: RequestBody? = null): String =
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(url("api/v1/$path", query))
                .method(method, body ?: if (method == "POST" || method == "PUT") ByteArray(0).toRequestBody(null) else null)
                .header("Accept", "application/json")
                .apply { token?.let { header("Authorization", "Bearer $it") } }
                .build()
            val response = try {
                http.newCall(request).execute()
            } catch (e: SSLException) {
                throw ApiException("Die sichere Verbindung wurde abgelehnt. Ist das Zertifikat des Servers auf diesem Gerät als vertrauenswürdig eingerichtet? (${e.message})")
            } catch (e: IOException) {
                throw ApiException("Der Server ist nicht erreichbar. Besteht eine Verbindung zum Schulnetz oder VPN? (${e.message})")
            }
            response.use {
                val text = it.body?.string().orEmpty()
                if (it.isSuccessful) return@withContext text
                val message = runCatching { json.decodeFromString<ApiError>(text).error }.getOrNull()
                    ?.takeIf { m -> m.isNotBlank() }
                    ?: when (it.code) {
                        404 -> "Nicht gefunden. Unterstützt der Server die App-Schnittstelle bereits?"
                        413 -> "Die Datei ist zu groß."
                        else -> "Der Server hat mit Fehler ${it.code} geantwortet."
                    }
                if (it.code == 401 && token != null) throw UnauthorizedException(message)
                throw ApiException(message, it.code)
            }
        }

    private inline fun <reified T> encode(value: T): RequestBody = json.encodeToString(value).toRequestBody(JSON_TYPE)

    suspend fun login(password: String, otp: String, device: String): LoginResponse =
        json.decodeFromString(call("POST", "login", body = encode(LoginRequest(password, otp, device))))

    suspend fun logout() { call("POST", "logout") }

    suspend fun me(): Me = json.decodeFromString(call("GET", "me"))

    suspend fun day(date: String?): Day = json.decodeFromString(call("GET", "day", mapOf("date" to date)))

    suspend fun entries(query: String?, type: String?, page: Int, inbox: Boolean = false): EntryPage =
        json.decodeFromString(
            call("GET", "entries", mapOf("q" to query, "type" to type, "page" to page.toString(), "inbox" to if (inbox) "1" else null))
        )

    suspend fun entry(id: Int): Entry = json.decodeFromString(call("GET", "entries/$id"))

    suspend fun createEntry(draft: EntryDraft): Entry = json.decodeFromString(call("POST", "entries", body = encode(draft)))

    suspend fun updateEntry(id: Int, draft: EntryDraft): Entry =
        json.decodeFromString(call("PUT", "entries/$id", body = encode(draft)))

    suspend fun upload(entryId: Int, name: String, mime: String, bytes: ByteArray): Entry {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("file", name, bytes.toRequestBody(mime.toMediaType()))
            .build()
        return json.decodeFromString(call("POST", "entries/$entryId/attachments", body = body))
    }

    /** Anhang herunterladen; der Server schickt die entschlüsselte Datei. */
    suspend fun download(attachmentId: Int): ByteArray = withContext(Dispatchers.IO) {
        val request = Request.Builder().url(url("api/v1/attachments/$attachmentId"))
            .apply { token?.let { header("Authorization", "Bearer $it") } }.build()
        val response = try {
            http.newCall(request).execute()
        } catch (e: IOException) {
            throw ApiException("Der Server ist nicht erreichbar. (${e.message})")
        }
        response.use {
            if (it.code == 401) throw UnauthorizedException("Bitte in der App erneut anmelden.")
            if (!it.isSuccessful) throw ApiException("Der Anhang konnte nicht geladen werden (${it.code}).", it.code)
            it.body?.bytes() ?: ByteArray(0)
        }
    }

    suspend fun tasks(filter: String, query: String?): List<Task> =
        json.decodeFromString<TaskList>(call("GET", "tasks", mapOf("filter" to filter, "q" to query))).items

    suspend fun createTask(draft: TaskDraft): Task = json.decodeFromString(call("POST", "tasks", body = encode(draft)))

    suspend fun toggleTask(id: Int): Task = json.decodeFromString(call("POST", "tasks/$id/toggle"))

    suspend fun autocomplete(kind: String, query: String): List<Item> =
        json.decodeFromString<ItemPage>(call("GET", "autocomplete/$kind", mapOf("q" to query))).items
}
