package de.sljournal.android.ui.components

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

private val GERMAN = Locale.GERMANY
private val SHORT = DateTimeFormatter.ofPattern("dd.MM.yyyy", GERMAN)

fun parseDate(iso: String?): LocalDate? = iso?.takeIf { it.length >= 10 }?.let { runCatching { LocalDate.parse(it.take(10)) }.getOrNull() }

/** 27.09.2026 */
fun shortDate(iso: String?): String = parseDate(iso)?.format(SHORT) ?: "Ohne Datum"

/** Sonntag, 27. September 2026 */
fun longDate(iso: String?): String = parseDate(iso)?.let {
    it.dayOfWeek.getDisplayName(TextStyle.FULL, GERMAN) + ", " + it.dayOfMonth + ". " +
        it.month.getDisplayName(TextStyle.FULL, GERMAN) + " " + it.year
} ?: ""

fun weekdayShort(iso: String?): String = parseDate(iso)?.dayOfWeek?.getDisplayName(TextStyle.SHORT, GERMAN)?.uppercase(GERMAN) ?: ""

fun dayOfMonth(iso: String?): String = parseDate(iso)?.dayOfMonth?.toString() ?: ""

/** Relativ zu heute: „Heute“, „Gestern“, „Morgen“ oder das kurze Datum. */
fun relativeDate(iso: String?, today: LocalDate = LocalDate.now()): String {
    val date = parseDate(iso) ?: return "Ohne Datum"
    return when (date) {
        today -> "Heute"
        today.minusDays(1) -> "Gestern"
        today.plusDays(1) -> "Morgen"
        else -> date.format(SHORT)
    }
}

fun formatSize(bytes: Long): String = when {
    bytes >= 1024 * 1024 -> String.format(GERMAN, "%.1f MB", bytes / 1024.0 / 1024.0)
    bytes >= 1024 -> String.format(GERMAN, "%.0f KB", bytes / 1024.0)
    else -> "$bytes Byte"
}
