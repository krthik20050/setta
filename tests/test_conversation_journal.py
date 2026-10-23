import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from src.conversation_journal import ConversationJournal


class JournalTests(unittest.TestCase):
    def test_local_audio_transcript_and_generated_reply_survive_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = ConversationJournal(root, 'test-session')
            turn = journal.new_turn()
            audio = b'RIFF-test-recording'
            journal.audio(turn, audio)
            journal.event(turn, 'transcription', text='I am going to wash the laundry', language='en-IN')
            journal.event(turn, 'reply_generated', text='Okay.')
            ConversationJournal(root, 'new-session')
            with closing(sqlite3.connect(root/'events.sqlite')) as db:
                rows = db.execute('SELECT turn_id,stage,details FROM events ORDER BY id').fetchall()
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row[0] == turn for row in rows))
            self.assertEqual((root/'audio'/turn/'input.wav').read_bytes(), audio)
            self.assertEqual(json.loads(rows[1][2])['text'], 'I am going to wash the laundry')
