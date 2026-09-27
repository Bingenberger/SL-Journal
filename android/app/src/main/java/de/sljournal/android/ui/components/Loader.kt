package de.sljournal.android.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import de.sljournal.android.AppViewModel
import de.sljournal.android.data.JournalApi

sealed interface Load<out T> {
    data object Loading : Load<Nothing>
    data class Ok<T>(val value: T) : Load<T>
    data class Failed(val message: String) : Load<Nothing>
}

class Loader<T>(state: Load<T>, val reload: () -> Unit, val set: (T) -> Unit) {
    val state: Load<T> = state
    val value: T? get() = (state as? Load.Ok<T>)?.value
}

/**
 * Lädt Daten vom Server, sobald sich einer der Schlüssel ändert oder anderswo
 * gespeichert wurde. Vorhandene Daten bleiben beim Neuladen sichtbar.
 */
@Composable
fun <T> rememberLoader(app: AppViewModel, vararg keys: Any?, block: suspend (JournalApi) -> T): Loader<T> {
    val revision by app.revision.collectAsState()
    var manual by remember { mutableIntStateOf(0) }
    var state by remember(*keys) { mutableStateOf<Load<T>>(Load.Loading) }
    LaunchedEffect(*keys, revision, manual) {
        val api = app.api ?: return@LaunchedEffect
        state = try {
            Load.Ok(block(api))
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            val message = app.handle(e)
            if (state is Load.Ok) state else Load.Failed(message)
        }
    }
    return Loader(state, reload = { manual++ }, set = { state = Load.Ok(it) })
}
