# standard libraries
import logging
import unittest

# third party libraries
# None

# local libraries
from nion.ui import Geometry


class TestGeometryClass(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_fit_to_size(self):
        eps = 0.0001
        rects = []
        sizes = []
        rects.append( ((0, 0), (300, 700)) )
        sizes.append( (600, 1200) )
        rects.append( ((0, 0), (300, 700)) )
        sizes.append( (1200, 600) )
        rects.append( ((0, 0), (600, 800)) )
        sizes.append( (700, 1300) )
        rects.append( ((0, 0), (600, 800)) )
        sizes.append( (1300, 700) )
        for rect, size in zip(rects, sizes):
            fit = Geometry.fit_to_size(rect, size)
            self.assertTrue(abs(float(fit[1][1])/float(fit[1][0]) - float(size[1])/float(size[0])) < eps)

    def test_int_point_ne(self):
        p1 = Geometry.IntPoint(x=0, y=1)
        p2 = Geometry.IntPoint(x=0, y=2)
        self.assertNotEqual(p1, p2)

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
