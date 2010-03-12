#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from lxml import etree
from . import xhtml2odt

class ParagraphElements(unittest.TestCase):

    def test_p1(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>Test</p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Test</text:p>
"""

    def test_p_containing_ul(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p><ul><li>Test</li></ul></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:list xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="List_20_1">
  <text:list-item>
    <text:p text:style-name="list-item-bullet">Test</text:p>
  </text:list-item>
</text:list>
"""

    def test_p_containing_ol(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p><ol><li>Test</li></ol></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:list xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Numbering_20_1">
  <text:list-item>
    <text:p text:style-name="list-item-number">Test</text:p>
  </text:list-item>
</text:list>
"""

    def test_p_containing_blockquote(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p><blockquote><p>Test</p></blockquote></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Quotations">Test</text:p>
"""

    def test_p_containing_pre(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p><pre>Test</pre></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Test</text:p>
"""

    def test_p_containing_text_and_block(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>Top text<pre>Test</pre>Bottom text</p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Top text</text:p>""" + \
"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Test</text:p>""" + \
"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Bottom text</text:p>
"""

    def test_p_containing_text_and_inline_and_block(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>Top <sup>sup text</sup> text<pre>Test</pre></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Top """ + \
"""<text:span text:style-name="sup">sup text</text:span> text</text:p>""" + \
"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Test</text:p>
"""

#    def test_p_containing_text_and_2_blocks(self):
#        # Unsupported yet
#        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>Top text<pre>Block 1</pre>Middle text<pre>Block 2</pre>Bottom text</p></html>'
#        odt = xhtml2odt(html)
#        print odt
#        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
#<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Top text</text:p>""" + \
#"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Block 1</text:p>""" + \
#"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Middle text</text:p>""" + \
#"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Block 2</text:p>""" + \
#"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Bottom text</text:p>
#"""

    def test_p_containing_text_and_2_inlines(self):
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p>Top text<sup>inline text 1</sup>Middle text<sup>inline text 2</sup>Bottom text<pre>Test</pre></p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Text_20_body">Top text""" + \
"""<text:span text:style-name="sup">inline text 1</text:span>Middle text""" + \
"""<text:span text:style-name="sup">inline text 2</text:span>Bottom text</text:p>""" + \
"""<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="Preformatted_20_Text">Test</text:p>
"""

    def test_p_center1(self):
        """<p> tag: with text-align: center (space)"""
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p style="text-align: center">Test</p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="center">Test</text:p>
"""

    def test_p_center2(self):
        """<p> tag: with text-align:center (no space)"""
        html = '<html xmlns="http://www.w3.org/1999/xhtml"><p style="text-align:center">Test</p></html>'
        odt = xhtml2odt(html)
        print odt
        assert str(odt) == """<?xml version="1.0" encoding="utf-8"?>
<text:p xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" text:style-name="center">Test</text:p>
"""


if __name__ == '__main__':
    unittest.main()
