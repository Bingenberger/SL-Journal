package de.sljournal.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Farben aus journal/static/style.css der Weboberfläche.
private val Teal = Color(0xFF25766E)
private val TealDark = Color(0xFF185C56)
private val Soft = Color(0xFFEAF3F0)
private val Ink = Color(0xFF233B40)
private val Muted = Color(0xFF7B888C)
private val Line = Color(0xFFE5EAEB)
private val Background = Color(0xFFF7F8FA)
private val Orange = Color(0xFFB4704A)
private val Red = Color(0xFFBA5C51)

private val Light = lightColorScheme(
    primary = Teal,
    onPrimary = Color.White,
    primaryContainer = Soft,
    onPrimaryContainer = TealDark,
    secondary = Color(0xFF60827B),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDF3F0),
    onSecondaryContainer = Color(0xFF2F4F48),
    tertiary = Orange,
    tertiaryContainer = Color(0xFFFBF1DA),
    onTertiaryContainer = Color(0xFF6E4E1E),
    error = Red,
    background = Background,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    surfaceVariant = Color(0xFFF0F3F4),
    onSurfaceVariant = Muted,
    surfaceContainer = Color.White,
    surfaceContainerLow = Background,
    surfaceContainerHigh = Color(0xFFF2F5F4),
    outline = Color(0xFFCDD9D6),
    outlineVariant = Line,
)

private val Dark = darkColorScheme(
    primary = Color(0xFF7CCBC0),
    onPrimary = Color(0xFF00382F),
    primaryContainer = Color(0xFF1D4F49),
    onPrimaryContainer = Color(0xFFCDEDE6),
    secondary = Color(0xFFA9CCC3),
    secondaryContainer = Color(0xFF2B4640),
    onSecondaryContainer = Color(0xFFD6ECE5),
    tertiary = Color(0xFFE7B98F),
    tertiaryContainer = Color(0xFF5A4121),
    onTertiaryContainer = Color(0xFFFBE3C6),
    error = Color(0xFFF2A69C),
    background = Color(0xFF111718),
    onBackground = Color(0xFFDDE4E3),
    surface = Color(0xFF172021),
    onSurface = Color(0xFFDDE4E3),
    surfaceVariant = Color(0xFF223032),
    onSurfaceVariant = Color(0xFFA2B0B2),
    outline = Color(0xFF52625F),
    outlineVariant = Color(0xFF2C3A3B),
)

@Composable
fun JournalTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dark else Light, content = content)
}
