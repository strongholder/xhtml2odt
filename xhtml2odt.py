#!/usr/bin/env python

"""
    xhtml2odt - XHTML to ODT XML transformation.
    Copyright (C) 2009-2010 Aurelien Bompard

This script can convert a wiki page to the OpenDocument Text (ODT) format,
standardized as ISO/IEC 26300:2006, and the native format of office suites such
as OpenOffice.org, KOffice, and others.

It uses a template ODT file which will be filled with the converted content of
the exported Wiki page.

Based on the work on docbook2odt, by Roman Fordinal
http://open.comsultia.com/docbook2odf/

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

import tempfile
import shutil
import re
import os
import sys
import zipfile
import urllib2
import urlparse
from glob import glob
from StringIO import StringIO
from optparse import OptionParser

import tidy
from lxml import etree
from PIL import Image

#pylint#: disable-msg=C0301,C0111

INSTALL_PATH = "."

INCH_TO_CM = 2.54
CHARSET = "utf-8"


class ODTExportError(Exception): pass

class HTMLFile(object):

    def __init__(self, options):
        self.options = options
        self.html = ""

    def read(self):
        in_file = open(self.options.input)
        self.html = in_file.read()
        in_file.close()
        self.cleanup()
        if self.options.htmlid:
            self.select_id()

    def cleanup(self):
        tidy_options = dict(output_xhtml=1, add_xml_decl=1, indent=1,
                            tidy_mark=0, #input_encoding=str(self.charset),
                            output_encoding='utf8', doctype='auto',
                            wrap=0, char_encoding='utf8')
        self.html = str(tidy.parseString(self.html, **tidy_options))
        # Replace nbsp with entity
        # http://www.mail-archive.com/analog-help@lists.meer.net/msg03670.html
        self.html = self.html.replace("&nbsp;", "&#160;")
        # Tidy creates newlines after <pre> (by indenting)
        self.html = re.sub('<pre([^>]*)>\n', '<pre\\1>', self.html)

    def select_id(self):
        html_tree = etree.fromstring(self.html)
        selected = html_tree.xpath("//*[@id='%s']" % self.options.htmlid)
        self.html = etree.tostring(selected[0], method="html")


class ODTFile(object):
    """Handles the conversion and production of an ODT file"""

    def __init__(self, options):
        self.options = options
        self.template_dirs = []
        if options.tpldir:
            self.template_dirs.append(options.tpldir)
        self.template_dirs.append(
            os.path.join(INSTALL_PATH, "styles")
        )
        self.xml = {
            "content": "",
            "styles": "",
        }
        self.tmpdir = tempfile.mkdtemp(prefix="xhtml2odt-")

    def open(self):
        self.zfile = zipfile.ZipFile(self.options.template, "r")
        for name in self.zfile.namelist():
            fname = os.path.join(self.tmpdir, name)
            if not os.path.exists(os.path.dirname(fname)):
                os.makedirs(os.path.dirname(fname))
            if name[-1] == "/":
                if not os.path.exists(fname):
                    os.mkdir(fname)
                continue
            fname_h = open(fname, "w")
            fname_h.write(self.zfile.read(name))
            fname_h.close()
        for xmlfile in self.xml:
            self.xml[xmlfile] = self.zfile.read("%s.xml" % xmlfile)

    def import_xhtml(self, xhtml):
        odt = self.xhtml_to_odt(xhtml)
        self.insert_content(odt)
        self.add_styles()

    def xhtml_to_odt(self, xhtml):
        xsl_dir = os.path.join(INSTALL_PATH, 'xsl')
        xslt_doc = etree.parse(os.path.join(xsl_dir, "xhtml2odt.xsl"))
        transform = etree.XSLT(xslt_doc)
        xhtml = self.handle_images(xhtml)
        xhtml = self.handle_links(xhtml)
        xhtml = etree.fromstring(xhtml) # must be valid xml at this point
        params = {
            "url": "/",
            "heading_minus_level": str(self.options.top_header_level - 1),
        }
        if self.options.verbose:
            params["debug"] = "1"
        if self.options.img_width:
            params["img_default_width"] = etree.XSLT.strparam(
                                            self.options.img_width)
        if self.options.img_height:
            params["img_default_height"] = etree.XSLT.strparam(
                                            self.options.img_height)
        odt = transform(xhtml, **params)
        return str(odt).replace('<?xml version="1.0" encoding="utf-8"?>','')

    def handle_images(self, xhtml):
        # Handle local images
        xhtml = re.sub('<img [^>]*src="([^"]+)"[^>]*>',
                      self.handle_local_img, xhtml)
        # Handle remote images
        if self.options.with_network:
            xhtml = re.sub('<img [^>]*src="(https?://[^"]+)"[^>]*>',
                          self.handle_remote_img, xhtml)
        #print xhtml
        return xhtml

    def handle_local_img(self, img_mo):
        log("handling local image: %s" % img_mo.group(1), self.options.verbose)
        src = img_mo.group(1)
        if src.count("://") and not src.startswith("file://"):
            # This is an absolute link, don't touch it
            return img_mo.group()
        if src.startswith("file://"):
            filename = src[7:]
        elif src.startswith("/"):
            filename = src
        else: # relative link
            filename = os.path.join(os.path.dirname(self.options.input), src)
        if os.path.exists(filename):
            return self.handle_img(img_mo.group(), src, filename)
        if src.startswith("file://") or not self.options.url:
            # There's nothing we can do here
            return img_mo.group()
        newsrc = urlparse.urljoin(self.options.url, os.path.normpath(src))
        if not self.options.with_network:
            # Don't download it, just update the URL
            return img_mo.group().replace(src, newsrc)
        try:
            tmpfile = self.download_img(newsrc)
        except (urllib2.HTTPError, urllib2.URLError):
            log("Failed getting %s" % newsrc, self.options.verbose)
            return img_mo.group()
        ret = self.handle_img(img_mo.group(), src, tmpfile)
        os.remove(tmpfile)
        return ret

    def handle_remote_img(self, img_mo):
        log('handling remote image: %s' % img_mo.group(), self.options.verbose)
        src = img_mo.group(1)
        try:
            tmpfile = self.download_img(src)
        except (urllib2.HTTPError, urllib2.URLError):
            return img_mo.group()
        ret = self.handle_img(img_mo.group(), src, tmpfile)
        os.remove(tmpfile)
        return ret

    def download_img(self, src):
        """
        Download the image to a temporary location
        """
        log('Downloading image: %s' % src, self.options.verbose)
        # TODO: proxy support
        remoteimg = urllib2.urlopen(src)
        tmpimg_fd, tmpfile = tempfile.mkstemp()
        tmpimg = os.fdopen(tmpimg_fd, 'w')
        tmpimg.write(remoteimg.read())
        tmpimg.close()
        remoteimg.close()
        return tmpfile

    def handle_img(self, full_tag, src, filename):
        log('Importing image: %s' % filename, self.options.verbose)
        if not os.path.exists(filename):
            raise ODTExportError('Image "%s" is not readable or does not exist'
                                 % filename)
        # TODO: generate a filename (with tempfile.mkstemp) to avoid weird
        # filenames. Maybe use img.format for the extension
        if not os.path.exists(os.path.join(self.tmpdir, "Pictures")):
            os.mkdir(os.path.join(self.tmpdir, "Pictures"))
        shutil.copy(filename, os.path.join(self.tmpdir, "Pictures",
                                           os.path.basename(filename)))
        full_tag = full_tag.replace('src="%s"' % src,
                    'src="Pictures/%s"' % os.path.basename(filename))
        try:
            img = Image.open(filename)
        except IOError:
            log('Failed to identify image: %s' % filename,
                self.options.verbose)
        else:
            width, height = img.size
            log('Detected size: %spx x %spx' % (width, height),
                self.options.verbose)
            width_mo = re.search('width="([0-9]+)(?:px)?"', full_tag)
            height_mo = re.search('height="([0-9]+)(?:px)?"', full_tag)
            if width_mo and height_mo:
                log('Forced size: %spx x %spx.' % (width_mo.group(),
                        height_mo.group()), self.options.verbose)
                width = float(width_mo.group(1)) / self.options.img_dpi * INCH_TO_CM
                height = float(height_mo.group(1)) / self.options.img_dpi * INCH_TO_CM
                full_tag = full_tag.replace(width_mo.group(), "")\
                                   .replace(height_mo.group(), "")
            elif width_mo and not height_mo:
                newwidth = float(width_mo.group(1)) / float(self.options.img_dpi) * INCH_TO_CM
                height = height * newwidth / width
                width = newwidth
                log('Forced width: %spx. Size will be: %scm x %scm' %
                    (width_mo.group(1), width, height), self.options.verbose)
                full_tag = full_tag.replace(width_mo.group(), "")
            elif not width_mo and height_mo:
                newheight = float(height_mo.group(1)) / float(self.options.img_dpi) * INCH_TO_CM
                width = width * newheight / height
                height = newheight
                log('Forced height: %spx. Size will be: %scm x %scm' %
                    (height_mo.group(1), height, width), self.options.verbose)
                full_tag = full_tag.replace(height_mo.group(), "")
            else:
                width = width / float(self.options.img_dpi) * INCH_TO_CM
                height = height / float(self.options.img_dpi) * INCH_TO_CM
                log('Size converted to: %scm x %scm' % (height, width),
                        self.options.verbose)
            full_tag = full_tag.replace('<img',
                    '<img width="%scm" height="%scm"' % (width, height))
        return full_tag

    def handle_links(self, xhtml):
        """Turn relative links into absolute links"""
        # Handle local images
        xhtml = re.sub('<a [^>]*href="([^"]+)"',
                      self.handle_relative_links, xhtml)
        return xhtml

    def handle_relative_links(self, link_mo):
        href = link_mo.group(1)
        if href.startswith("file://") or not self.options.url:
            # There's nothing we can do here
            return link_mo.group()
        if href.count("://"):
            # This is an absolute link, don't touch it
            return link_mo.group()
        log("handling relative link: %s" % href, self.options.verbose)
        newhref = urlparse.urljoin(self.options.url, os.path.normpath(href))
        return link_mo.group().replace(href, newhref)

    def insert_content(self, content):
        if self.options.replace_keyword and \
            self.xml["content"].count(self.options.replace_keyword) > 0:
            self.xml["content"] = re.sub(
                    "<text:p[^>]*>" +
                    re.escape(self.options.replace_keyword)
                    +"</text:p>", content, self.xml["content"])
        else:
            self.xml["content"] = self.xml["content"].replace(
                '</office:text>',
                content + '</office:text>')
        # Cut unwanted text
        if self.options.cut_start \
                and self.xml["content"].count(self.options.cut_start) > 0 \
                and self.options.cut_stop \
                and self.xml["content"].count(self.options.cut_stop) > 0:
            self.xml["content"] = re.sub(
                    re.escape(self.options.cut_start)
                    + ".*" +
                    re.escape(self.options.cut_stop),
                    "", self.xml["content"])

    def add_styles(self):
        xsl_dir = os.path.join(INSTALL_PATH, 'xsl')
        xslt_doc = etree.parse(os.path.join(xsl_dir, "styles.xsl"))
        transform = etree.XSLT(xslt_doc)
        contentxml = etree.fromstring(self.xml["content"])
        stylesxml = etree.fromstring(self.xml["styles"])
        params = {}
        if self.options.verbose:
            params["debug"] = "1"
        self.xml["content"] = str(transform(contentxml, **params))
        self.xml["styles"] = str(transform(stylesxml, **params))

    def compile(self):
        # Store the new content
        for xmlfile in self.xml:
            xmlf = open(os.path.join(self.tmpdir, "%s.xml" % xmlfile), "w")
            xmlf.write(self.xml[xmlfile])
            xmlf.close()

    def _build_zip(self, document):
        newzf = zipfile.ZipFile(document, "w", zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(self.tmpdir):
            for file in files:
                realpath = os.path.join(root, file)
                internalpath = os.path.join(root.replace(self.tmpdir, ""), file)
                newzf.write(realpath, internalpath)
        newzf.close()

    def save(self, output=None):
        self.compile()
        if output:
            document = output
        else:
            document = StringIO()
        self._build_zip(document)
        shutil.rmtree(self.tmpdir)
        if not output:
            return document.getvalue()


def log(msg, verbose=False):
    if verbose:
        sys.stderr.write(msg+"\n")

def get_options():
    usage = "usage: %prog [options] -i input -o output -t template.odt"
    parser = OptionParser(usage=usage)
    parser.add_option("-i", "--input", dest="input", metavar="FILE",
                      help="Read the html from this file")
    parser.add_option("-o", "--output", dest="output", metavar="FILE",
                      help="Location of the output ODT file")
    parser.add_option("-t", "--template", dest="template", metavar="FILE",
                      help="Location of the template ODT file")
    parser.add_option("-u", "--url", dest="url",
                      help="Use this URL for relative links")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", default=False,
                      help="Show what's going on")
    parser.add_option("--html-id", dest="htmlid", metavar="ID",
                      help="Only export from the element with this ID")
    parser.add_option("--replace", dest="replace_keyword",
                      default="ODT-INSERT", metavar="KEYWORD",
                      help="Keyword to replace in the ODT template "
                      "(default is %default)")
    parser.add_option("--cut-start", dest="cut_start",
                      default="ODT-CUT-START", metavar="KEYWORD",
                      help="Keyword to start cutting text from the ODT "
                      "template (default is %default)")
    parser.add_option("--cut-stop", dest="cut_stop",
                      default="ODT-CUT-STOP", metavar="KEYWORD",
                      help="Keyword to stop cutting text from the ODT "
                      "template (default is %default)")
    parser.add_option("--top-header-level", dest="top_header_level",
                      type="int", default="1", metavar="LEVEL",
                      help="Level of highest header in the HTML "
                      "(default is %default)")
    parser.add_option("--img-default-width", dest="img_width",
                      metavar="WIDTH", default="8cm",
                      help="Default image width (default is %default)")
    parser.add_option("--img-default-height", dest="img_height",
                      metavar="HEIGHT", default="6cm",
                      help="Default image height (default is %default)")
    parser.add_option("--dpi", dest="img_dpi", type="int",
                      default=96, metavar="DPI", help="Screen resolution "
                      "in Dots Per Inch (default is %default)")
    parser.add_option("--no-network", dest="with_network",
                      action="store_false", default=True,
                      help="Do not download remote images")
    parser.add_option("--tpldir", dest="tpldir",
                      help="Override templates directory")
    options, args = parser.parse_args()
    if len(args) > 0:
        parser.error("illegal arguments: %s"% ", ".join(args))
    if not options.input:
        parser.error("No input provided")
    if not options.output:
        parser.error("No output provided")
    if not options.template:
        parser.error("No ODT template provided")
    if not os.path.exists(options.input):
        parser.error("Can't find input file: %s" % options.input)
    if not os.path.exists(options.template):
        parser.error("Can't find template file: %s" % options.template)
    return options, args

def main():
    options, args = get_options()
    htmlfile = HTMLFile(options)
    htmlfile.read()
    odtfile = ODTFile(options)
    odtfile.open()
    odtfile.import_xhtml(htmlfile.html)
    odtfile.save(options.output)

if __name__ == '__main__':
    main()

