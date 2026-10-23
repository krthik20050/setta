import tempfile
import unittest
from pathlib import Path
import numpy as np
from src.face_id import FaceID
from src.paths import PROJECT_ROOT

class FaceGalleryTests(unittest.TestCase):
    def setUp(self):
        parent = PROJECT_ROOT / 'runtime' / 'face-gallery-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.faces = FaceID(self.folder, '')

    def test_thumbnail_samples_survive_restart_and_remove(self):
        embedding = np.arange(1, 17)
        preview = np.zeros((90, 70, 3), dtype=np.uint8)
        self.faces.register_face('Father', embedding, preview)
        self.faces.register_face('Father', embedding + .2)
        restarted = FaceID(self.folder, '')
        rows = restarted.list_faces()
        self.assertEqual(rows[0]['name'], 'Father')
        self.assertEqual(rows[0]['samples'], 2)
        self.assertTrue(rows[0]['thumbnail'].startswith(b'\xff\xd8'))
        restarted.remove_face('Father')
        self.assertEqual(restarted.list_faces(), [])
        self.assertEqual(FaceID(self.folder, '').list_faces(), [])
        self.assertFalse((self.folder / 'Father.jpg').exists())

    def test_legacy_embedding_has_no_invented_preview(self):
        np.save(self.folder / 'Mother.npy', np.arange(1, 17))
        rows = FaceID(self.folder, '').list_faces()
        self.assertEqual(rows[0]['samples'], 1)
        self.assertIsNone(rows[0]['thumbnail'])

    def test_remove_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            self.faces.remove_face('../private')
    def test_owner_portrait_persists_without_changing_recognition_samples(self):
        from PIL import Image
        self.faces.register_face('Karthik', np.arange(1, 17))
        source = self.folder / 'portrait source.png'
        Image.new('RGB', (500, 700), '#709080').save(source)
        before = (self.folder / 'Karthik.npy').read_bytes()
        self.faces.set_portrait('Karthik', source)
        self.assertEqual(before, (self.folder / 'Karthik.npy').read_bytes())
        row = FaceID(self.folder, '').list_faces()[0]
        self.assertTrue(row['thumbnail'])
        self.assertEqual(row['samples'], 1)
        from src.people_portrait import portrait_tile
        tile = portrait_tile(row['thumbnail'], 'Karthik')
        self.assertEqual(tile.size, (180, 232))
        self.assertEqual(tile.getpixel((0, 0))[3], 0)

    def test_missing_preview_backfill_requires_camera_and_repeated_strong_matches(self):
        embedding = np.arange(1, 17)
        self.faces.register_face('Father', embedding)
        image = np.random.default_rng(17).integers(45, 210, (100,100,3), dtype=np.uint8)
        self.assertFalse(self.faces.save_missing_preview('Father', embedding, image, now=1))
        self.faces.capture_previews = True
        self.assertEqual([self.faces.save_missing_preview('Father', embedding, image, now=t) for t in (1,3,5)], [False,False,True])
        row = self.faces.list_faces()[0]
        self.assertEqual(row['samples'], 1)
        self.assertTrue(row['thumbnail'])
        original = row['thumbnail']
        self.assertFalse(self.faces.save_missing_preview('Father', embedding, image, now=10))
        self.assertEqual(self.faces.list_faces()[0]['thumbnail'], original)

    def test_unknown_and_ambiguous_matches_do_not_fill_a_photo(self):
        embedding = np.arange(1,17)
        self.faces.register_face('Father', embedding)
        self.faces.register_face('Uncle', embedding+.001)
        self.faces.capture_previews = True
        image = np.random.default_rng(17).integers(45,210,(100,100,3),dtype=np.uint8)
        self.assertFalse(self.faces.save_missing_preview('Unknown', embedding, image, now=1))
        for stamp in (1,3,5):
            self.assertFalse(self.faces.save_missing_preview('Father', embedding, image, now=stamp))
        self.assertIsNone(self.faces.list_faces()[0]['thumbnail'])
    def test_copied_reference_album_is_not_loaded_into_real_people(self):
        import json
        from PIL import Image
        album=self.folder/'people_album'; album.mkdir()
        (album/'people.json').write_text(json.dumps(['Copied reference']),encoding='utf-8')
        Image.new('RGB',(200,300),'#527896').save(album/'reference.jpg')
        faces=FaceID(self.folder/'known_faces','')
        self.assertEqual(faces.list_faces(),[])
        self.assertEqual(faces.known_face_embeddings,{})

    def test_portrait_render_handles_odd_heights(self):
        import io
        from PIL import Image
        from src.people_portrait import portrait_tile
        buffer=io.BytesIO()
        Image.new('RGB',(200,300),'#567890').save(buffer,format='PNG')
        self.assertEqual(portrait_tile(buffer.getvalue(),'Karthik',(179,237)).size,(179,237))

    def test_face_avatar_is_compact_and_circular(self):
        import io
        from PIL import Image
        from src.people_portrait import face_avatar
        buffer=io.BytesIO()
        Image.new('RGB',(240,160),'#567890').save(buffer,format='PNG')
        avatar=face_avatar(buffer.getvalue(),88)
        self.assertEqual(avatar.size,(88,88))
        self.assertEqual(avatar.getpixel((0,0))[3],0)
        self.assertEqual(avatar.getpixel((44,44))[3],255)
