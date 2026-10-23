import unittest
from unittest.mock import Mock

from src.thought_bubble import cloud_points, draw_cloud, float_offset, wrap_pages
from src.speaking_face import mouth_geometry


class BubbleTests(unittest.TestCase):
    def test_cloud_uses_curves_and_thought_dots_not_a_rectangle(self):
        canvas=Mock()
        draw_cloud(canvas,280,'Thinking…',('Nirmala UI',10))
        canvas.create_rectangle.assert_not_called()
        self.assertEqual(canvas.create_oval.call_count,2)
        self.assertTrue(canvas.create_polygon.call_args.kwargs['smooth'])
        self.assertEqual(canvas.create_text.call_args.kwargs['text'],'Thinking…')

    def test_cloud_fits_reserved_space_and_float_is_subtle(self):
        points=cloud_points(264,78)
        self.assertTrue(all(8<=x<=272 for x in points[::2]))
        self.assertTrue(all(8<=y<=86 for y in points[1::2]))
        self.assertTrue(all(abs(float_offset(x/10))<=1.4 for x in range(100)))

    def test_pixel_width_pagination_preserves_words(self):
        text='One complete sentence. Another complete sentence with English മലയാളം words.'
        pages=wrap_pages(text,lambda s:len(s)*7,width=105,max_lines=3)
        self.assertEqual(' '.join(pages).split(),text.split())
        self.assertTrue(all(len(page.split('\n'))<=3 for page in pages))

    def test_mouth_opens_without_moving_character_anchor(self):
        boxes=[mouth_geometry(i) for i in range(6)]
        self.assertGreater(len(set(boxes)),3)
        self.assertTrue(all((a+c)/2==134 and (b+d)/2==154 for a,b,c,d in boxes))
