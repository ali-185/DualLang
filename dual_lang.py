# Google Translator
import goslate

# Std libs
import argparse
import os
import re
import shutil
import sys
import tempfile
import zipfile

from time import sleep

class Converter:
    """ Converts to dual language files. Putting translated text after 
    certain delimiters.
    
    For example:
    
    <p><span>The dog, which was <bold>very</bold> scary, bit me.<span> So I
    ran.</p>
    
    Will become (the translated text is upper case):
    
    <p><span>The dog, THE DOG, which was <bold>very</bold> scary, WHICH WAS
    <bold>VERY</bold> SCARY, bit me. BIT ME.<span> So I ran. SO I RAN.</p>
    
    I have found with experimentation that this is the most pleasing way to
    read dual language texts. The phrases are long enough such that you can
    understand the story, yet short enough that you can remember what is being
    translated.
    """
    def __init__(self, in_lang, out_lang, delimiters=None):
        self._goslate = goslate.Goslate()
        # These tags are used internally before 
        # Google translating as a batch
        self._translate_open_tag = '<translate>'
        self._translate_close_tag = "<\translate>"
        
        self.in_lang = in_lang
        self.out_lang = out_lang
        if delimiters:
            self.delims = delimiters
        else:
            self.delims = ['.', '!', '?', ',', ';', ':', '"']
        
        self.percent_complete = 0
    
    def convert_epub(self, epub_file, epub_outfile):
        """ Converts an epub file. """
        # Extract epub
        tmp_dir = tempfile.mkdtemp()
        
        with zipfile.ZipFile(epub_file, 'r') as epub:
            epub.extractall(tmp_dir)
        
        total = 0
        for root, dirs, files in os.walk(tmp_dir):
            for file in files:
                if file.endswith('.html'):
                    total += 1
        
        # Update html files
        count = 0
        print('Translating html files...')
        for root, dirs, files in os.walk(tmp_dir):
            for file in files:
                if file.endswith('.html'):
                    self.percent_complete = count * 100 / total
                    print('Translating ' + file + '...')
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf8') as file:
                        data = file.read()
                    new_data = self.convert_html(data)
                    with open(path, 'w', encoding='utf8') as file:
                        file.write(new_data)
                    count += 1
        
        # Create new epub
        print('Creating new epub...')
        with zipfile.ZipFile(epub_outfile, 'w') as epub_out:
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, tmp_dir) 
                    epub_out.write(path, rel_path)
        shutil.rmtree(tmp_dir)
        self.percent_complete = 100
    
    def convert_html(self, data):
        """ Converts the text (not the html tags) of the html data. 
        Note that '\n' characters are stripped.
        """
        def tag_para_match(match):
            return self._tag_html_para(match.group())
        
        def tag_body_match(match):
            return re.sub('<p[^>]*>(.*?)</p>', tag_para_match, match.group())
        
        flat_data = data.replace('\n', '')
        tagged_data = re.sub('<body[^>]*>(.*?)</body>', tag_body_match, flat_data)
        return self._translate_tagged(tagged_data)
    
    def _tag_html_para(self, string):
        """ Adds html translate tags to the data to be translated.
        
        This tags text, after each delimiter. It keeps the other html tags
        in both the original and the translated text.
        
        For example:
        
        <p><span>The dog, which was <bold>very</bold> scary, bit me.<span> So I
        ran.</p>
        
        Will become (the translate tags are <t></t> for brevity:
        
        <p><span>The dog, <t>The dog, </t> which was <bold>very</bold> scary, 
        <t>which was </t><bold><t>very</t></bold><t> scary</t>, bit me. <t>bit
        me</t>.<span> So I ran. <t> So I ran.</p>
        """
        tag_regex = re.compile('<[^>]*>')
        open_tag_regex = re.compile('<[^/>]*>')
        clos_tag_regex = re.compile('</[^>]*>')
        delims = ['.', '!', '?', ',', ';', ':', '"']
        
        open = ['']
        while string:
            if string.startswith('<'): # Tag
                tag = tag_regex.match(string).group()
                string = string[len(tag):]
                if open_tag_regex.match(tag):   # Opening tag
                    open += [tag]
                elif clos_tag_regex.match(tag): # Closing tag
                    open = open[:-2] + [open[-2] + open[-1] + tag]
                else:                           # Comment or self-closing tag
                    open[-1] += tag
            else: # Text
                count = 0    # Open - closed tags (always +ve)
                unopened = 0 # Missing open tags (extra closed tags are OK)
                original = ''
                translated = ''
                while True:
                    if count > 0:
                        regex = '[^<]*'
                    else:
                        regex = '[^<' + re.escape(''.join(delims)) + ']*'
                    text = re.match(regex, string).group()
                    string = string[len(text):]
                    original   += text
                    translated += self._add_translate_tags(text)
                    if string.startswith('<'): # Tag
                        tag = tag_regex.match(string).group()
                        string = string[len(tag):]
                        original   += tag
                        translated += tag
                        if open_tag_regex.match(tag):   # Opening tag
                            count += 1
                            unopened -= 1
                        elif clos_tag_regex.match(tag): # Closing tag
                            count = max(count - 1, 0)
                            unopened += 1
                    else: # Delim or EOF
                        original   += string[:1]
                        translated += string[:1]
                        string = string[1:]
                        break
                open_tags = ''.join(open[::-1][:unopened][::-1])
                open = open[::-1][unopened:][::-1]
                original   = open_tags + original
                translated = self._trim_html_text(open_tags) + translated
                open[-1] += original + " " + translated
        if len(open) > 1:
            raise "Error: Mismatching tags in epub. Is the epub corrupt?"
        return open[0]
    
    def _add_translate_tags(self, string):
        """ Add's translate tags to the string. """
        return self._translate_open_tag + string + self._translate_close_tag

    def _translate_tagged(self, data):
        """ Translates the tagged text. """
        t1 = re.escape(self._translate_open_tag)
        t2 = re.escape(self._translate_close_tag)
        regex = t1 + '(.*?)' + t2

        tagged_strs = re.findall(regex, data)
        
        # translate strips whitespace - inserting '|' to keep lines correlating
        line_modded = '|\n'.join(tagged_strs)
        translated_modded = self.translate_text(line_modded)
        translated_strs = translated_modded.replace('\n','').split('|')
        
        self._insert_tag_index = -1
        def insert_tag(match):
            self._insert_tag_index += 1
            return translated_strs[self._insert_tag_index]
        return re.sub(regex, insert_tag, data)

    def _trim_html_text(self, string):
        """ Removes the html text from a string, leaving only the tags. """
        def remove_group_2(match):
            return (match.group()[:match.start(2) - match.start(0)] +
                    match.group()[match.end(2) - match.start(0):])
        return re.sub('(^|>)([^<]*)(<|$)', remove_group_2, string)
    
    def translate_text(self, string):
        """ Wrapper around the goslate library, attempting translation 
        multiple times. Sometimes required with a bad internet connection.
        """
        max_attempts = 2
        for i in range(0, max_attempts):
            try:
                result = self._goslate.translate(string, self.out_lang, self.in_lang)
                if result:
                    return result
                else:
                    return string
            except:
                if i == max_attempts - 1:
                    try:
                        print('Error with google translate, skipping string: "' + string + '"')
                    except:
                        print('Error with google translate, skipping string.')
                    return string
                print('Error with google translate, retrying in 0.1 second(s)...')
            sleep(0.1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Converts an epub to a dual langauge epub.')
    parser.add_argument('in_lang', help='The input language code e.g. en, es')
    parser.add_argument('out_lang', help='The output langage code e.g. es, en')
    parser.add_argument('epub_file', help='The epub for converting')
    parser.add_argument('epub_outfile', help='The new epub name')
    args = parser.parse_args()
    
    converter = Converter(args.in_lang, args.out_lang)
    converter.convert_epub(args.epub_file, args.epub_outfile)