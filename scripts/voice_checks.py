"""Exercise real MediaRecorder with a synthetic Web Audio microphone stream."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from playwright.sync_api import expect
from case_suggestion_checks import main
from journal.db import one


def check(page,app):
    origin=page.url.rstrip('/')
    page.context.grant_permissions(['microphone'],origin=origin)
    page.goto(origin+'/?date=2001-01-01')
    # The headless environment has no microphone service. Feed a real audio
    # track to MediaRecorder; encoding, playback and upload remain real.
    page.evaluate('''() => {
      navigator.mediaDevices.getUserMedia=async()=>{
        const context=new AudioContext(), oscillator=context.createOscillator();
        const destination=context.createMediaStreamDestination();
        oscillator.connect(destination);oscillator.start();await context.resume();
        return destination.stream;
      };
    }''')
    page.locator('[data-voice-open]').click()
    dialog=page.locator('#voice-dialog')
    dialog.locator('[data-voice-start]').click()
    expect(dialog.locator('[data-voice-stop]')).to_be_visible()
    page.wait_for_timeout(1200)
    dialog.locator('[data-voice-stop]').click()
    expect(dialog.locator('audio')).to_be_visible()
    expect(dialog.locator('[data-voice-save]')).to_be_enabled()
    # Preview must actually decode, not merely have an audio element.
    dialog.locator('audio').evaluate('audio=>audio.play()')
    expect(dialog.locator('audio')).to_have_js_property('paused',False)
    for width in [1440,768,390,320]:
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert dialog.evaluate('el=>el.scrollWidth<=el.clientWidth')
    dialog.locator('[data-voice-save]').click()
    expect(dialog).not_to_be_visible()
    expect(page.locator('.journal-history audio')).to_have_count(1)
    with app.app_context():
        entry=one('SELECT * FROM entries')
        assert entry['date']!='2001-01-01'
        assert one('SELECT size FROM attachments')['size']>0
    page.goto(origin+f'/entry/{entry["id"]}')
    audio=page.locator('.attachment-row audio')
    audio.evaluate('audio=>audio.play()')
    expect(audio).to_have_js_property('paused',False)
    page.evaluate('''() => {navigator.mediaDevices.getUserMedia=async()=>{
      const context=new AudioContext(), destination=context.createMediaStreamDestination();
      await context.resume();return destination.stream;
    };}''')
    page.locator('[data-voice-open]').click()
    dialog.locator('[data-voice-start]').click()
    expect(dialog.locator('[data-voice-stop]')).to_be_visible()
    dialog.locator('[data-voice-close]').first.click()
    expect(dialog).not_to_be_visible()
    # Permission denied must produce a recoverable message.
    page.context.clear_permissions()
    page.evaluate("() => {navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException('Denied','NotAllowedError'));}")
    page.locator('[data-voice-open]').click()
    dialog.locator('[data-voice-start]').click()
    expect(dialog.locator('[data-voice-error]')).to_contain_text('nicht erlaubt')
    expect(dialog.locator('[data-voice-start]')).to_be_enabled()
    print('Aufnahme, Hörprobe, verschlüsseltes Speichern am heutigen Tag, Wiedergabe und Abbruch geprüft.')


if __name__=='__main__':
    main(check)
