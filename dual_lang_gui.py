# GUI elements
from tkinter import *
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.ttk import Progressbar
from tkinter.messagebox import showinfo, showwarning

# Running GUI and converter
from threading import Thread

# Check input
import os

# The dual language converter
from dual_lang import Converter

class MainWindow(Frame):
    languages = {'English': 'en', 'Spanish': 'es', 'Italian': 'it', 'German': 'de', 'French': 'fr'}
    padding = {'padx': 1, 'pady': 1}
    
    def __init__(self, *args, **kwargs):
        Frame.__init__(self, *args, **kwargs)
        
        self.master.title('Dual Language Convertor')
        
        def select_file_grid_row(row, text, button_text, filedialog):
            filename = StringVar() # Variable will update automatically if filename is changed
            language = StringVar() # Variable will update automatically if language is changed
            language.set("Select")
            
            def callback():
                # Do not change filename if dialog was cancelled.
                new_filename = filedialog()
                if new_filename:
                    filename.set(new_filename)
                    
            # Filename selectors
            Label(self, text=text).grid(row=row, column=0, sticky=W, **self.padding)
            Entry(self, textvariable=filename).grid(row=row, column=1, sticky=W+E, **self.padding)
            Button(self, text=button_text, command=callback).grid(row=row, column=2, sticky=W+E, **self.padding)
            # Language selectors
            Label(self, text='Language:').grid(row=row, column=3, sticky=W, **self.padding)
            OptionMenu(self, language, *self.languages.keys()).grid(row=row, column=4, sticky=W+E, **self.padding)
            
            return filename, language
        
        self.input_file, self.input_language = select_file_grid_row(0, 'Input File:', 'Open...', askopenfilename)
        self.output_file, self.output_language = select_file_grid_row(1, 'Output File:', 'Save As...', asksaveasfilename)
        
        Button(self, text='Convert', command=self.convert).grid(row=2, column=1, sticky=W+E, **self.padding)
        Button(self, text='Quit', command=self.quit).grid(row=2, column=2, sticky=W+E, **self.padding)
    
    def valid_input(self):
        """ Checks the input and displays a warning popup if something is invalid. """
        if not os.path.isfile(self.input_file.get()):
            showwarning(title='Error', message='Invalid input file.')
            return False
        elif not self.output_file.get():
            showwarning(title='Error', message='Invalid output file.')
            return False
        elif self.input_language.get() not in self.languages:
            showwarning(title='Error', message='Invalid input language.')
            return False
        elif self.output_language.get() not in self.languages:
            showwarning(title='Error', message='Invalid output language.')
            return False
        else:
            return True
    
    def convert(self):
        """ Runs the parallel_text converter in a thread with the current input. """
        if not self.valid_input():
            return
        
        popup = Toplevel(self)
        # Disable closing of the popup window
        popup.protocol('WM_DELETE_WINDOW', lambda : None)

        progress = IntVar()
        Label(popup, text='Converting Epub. This cannot be interrupted. Please wait...').grid(row=0, column=0)
        progressbar = Progressbar(popup, orient=HORIZONTAL, length=200, mode='determinate', variable=progress)
        progressbar.grid(row=1, column=0)
        # Run converter in thread
        converter = Converter(self.languages[self.input_language.get()], self.languages[self.output_language.get()])
        self._error = False
        def target():
            try:
                converter.convert_epub(self.input_file.get(), self.output_file.get())
            except Exception as e:
                self._error = True
                self._message = str(e)
        
        thread = Thread(target=target)
        thread.start()
        # Keep updating progress bar
        def update_progressbar():
            progress.set(converter.percent_complete)
            if thread.is_alive():
                popup.after(500, update_progressbar)
            else:
                progressbar.stop()
                popup.destroy()
                if self._error:
                    showinfo(title="Conversion failed", message=self._message)
                else:
                    showinfo(title="Conversion complete", message="Conversion complete.")
        
        popup.after(500, update_progressbar)
        # Disable the main window
        popup.transient(self)
        popup.grab_set()
        self.wait_window(popup)

if __name__ == "__main__":
    root = Tk()
    main = MainWindow(root)
    main.pack(side="top", fill="both", expand=True)
    root.mainloop()