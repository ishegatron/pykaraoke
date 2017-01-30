# ******************************************************************************
# ****                                                                      ****
# **** Copyright (C) 2016  Ishmal Lewis (ishegatron@github.com)             ****
# **** Copyright (C) 2010  PyKaraoke Development Team                       ****
# ****                                                                      ****
# **** This library is free software; you can redistribute it and/or        ****
# **** modify it under the terms of the GNU Lesser General Public           ****
# **** License as published by the Free Software Foundation; either         ****
# **** version 2.1 of the License, or (at your option) any later version.   ****
# ****                                                                      ****
# **** This library is distributed in the hope that it will be useful,      ****
# **** but WITHOUT ANY WARRANTY; without even the implied warranty of       ****
# **** MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU    ****
# **** Lesser General Public License for more details.                      ****
# ****                                                                      ****
# **** You should have received a copy of the GNU Lesser General Public     ****
# **** License along with this library; if not, write to the                ****
# **** Free Software Foundation, Inc.                                       ****
# **** 59 Temple Place, Suite 330                                           ****
# **** Boston, MA  02111-1307  USA                                          ****
# ******************************************************************************

from pykconstants import *
from pykenv import env
import pygame, sys, math, os, signal, string, subprocess, csv
from pattern.web import URL, DOM, plaintext, extension
import threading
from pykmanager import manager
from pykdb import globalSongDB
from os import read

# Python 2.3 and newer ship with optparse; older Python releases need "Optik"
# installed (optik.sourceforge.net)
try:
    import optparse
except:
    import Optik as optparse

if env == ENV_GP2X:
    import _cpuctrl as cpuctrl


class pykYTDownloader:
    """ There is only one instance of this class in existence during
    program execution, and it is never destructed until program
    termination.  This class manages searhing and downloading MP4 videos
    as MPG videos from YouTube."""

    def __init__(self):
        self.IsAvailable = False
        self.ErrorReason = ""

        self.procReturnCode = None
        self.proc = None

        ## url construct string text
        self.prefix_of_search_url = "https://www.youtube.com/results?search_query="
        self.prefix_of_result_url = "https://www.youtube.com/watch?v="

        if env == ENV_GP2X or env == ENV_POSIX:
            youtubeEXE = self.which("youtube-dl")
            if youtubeEXE != None:
                # print youtubeEXE # DEBUG
                self.IsAvailable = True
            else:
                self.ErrorReason = "This feature requires YoutubeDL, which cannot be found.  Please install it by running 'sudo apt-get install youtube-dl' in the terminal."
        else:
            self.ErrorReason = "This feature only works in Linux OS distributions."

            # print self.ErrorReason # DEBUG
            # print self.IsAvailable # DEBUG

    def SongExistsOnDisk(self, artist, title):
        fname = self.getSongFilePath(artist, title)
        return os.path.isfile(fname)

    def MassDownloadKaraokeSong(self, KaraokeMgr, csvFilePath, yielder, busyDlg):
        self.KaraokeMgr = KaraokeMgr
        self.BusyDlg = busyDlg
        self.Yielder = yielder
        self.BusyDlg.Show()
        
        with open(csvFilePath, 'rb') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',', quotechar='|')
            x = 0
            songList = list(spamreader)
            rowcount = len(songList)
            
            for row in songList:
                if self.BusyDlg.Clicked:
                    break
                    
                self.DownloadKaraokeSong(KaraokeMgr, row[0], row[1], "", yielder, busyDlg, rowcount, x)
                x = x + 1
                
        return True
        
    def DownloadKaraokeSong(self, KaraokeMgr, artist, title, url, yielder, busyDlg, totalCount=1, currentCount=0):
        self.KaraokeMgr = KaraokeMgr
        self.BusyDlg = busyDlg
        self.Yielder = yielder
        self.BusyDlg.Show()
        
        searchKey = artist + ' ' + title + ' Karaoke'
        fname = self.getSongFilePath(artist, title)
        partfname = fname.replace('.mpg', '.part')
        
        self.DialogStatusPrefix = "" + str(currentCount + 1) + " of " + str(totalCount) + ": "
        self.DialogBaseline = currentCount / float(totalCount)
        self.DialogProgressPart = 1 / float(totalCount)

        if self.SongExistsOnDisk(artist, title):
            try:
                self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Preparing overwrite...", self.__calculateProgress(0.05))
                self.Yielder.Yield()
                os.remove(fname)
            except OSError:
                self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Error removing file...", self.__calculateProgress(0.10))
                self.Yielder.Yield()
                pass
        elif os.path.isfile(partfname):
            try:
                self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Cleaning previous download...", self.__calculateProgress(0.05))
                self.Yielder.Yield()
                os.remove(partfname)
            except OSError:
                self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Error cleaning previous download...", self.__calculateProgress(0.10))
                self.Yielder.Yield()
                pass

        if url:
            cmd = 'sudo youtube-dl -f mp4 -o "' + fname + '" ' + url # + ' --verbose'
        else:
            self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Searching Youtube for " + searchKey + "...", self.__calculateProgress(0.20))
            self.BusyDlg.Fit()
            self.BusyDlg.CenterOnParent()
            self.Yielder.Yield() 
            
            url = self.getPopularVideo(searchKey)
            if not url:
                return False
            
            self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Found " + url + "...", self.__calculateProgress(0.30))
            self.BusyDlg.Fit()
            self.BusyDlg.CenterOnParent()
            self.Yielder.Yield()
            cmd = 'sudo youtube-dl -f mp4 -o "' + fname + '" ' + url # + ' --verbose'
        
        video_id = url.replace(self.prefix_of_result_url, '')
        
        if self.BusyDlg.Clicked:
            self.ErrorReason = "Cancelled. No song downloaded."
            return False
        
        self.__runCommand(cmd, video_id)        
        return True

    # Method to discover is an executeable exists on a system.
    def which(self, program):
        def is_exe(fpath):
            return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                path = path.strip('"')
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file

        return None

    def getSongFilePath(self, artist, title):
        mainFolder = globalSongDB.GetFolderList()[0]
        fileName = artist + " - " + title + ".mpg"
        return os.path.join(mainFolder, fileName)
        
    def __calculateProgress(self, progress):
        return self.DialogBaseline + (self.DialogProgressPart * progress)
        
    def __cleanOutput(self, output, video_id):
        output = output.strip()
        output = output.replace('[youtube] ','')
        output = output.replace('[download] ','')
        output = output.replace(video_id + ' ','')
        
        return output.strip()
        
    def __runCommand(self, cmd, video_id):
        """ This method runs in a sub-thread.  Its job is just to wait
        for the process to finish. """
        # assert self.procReturnCode == None
        sys.stdout.flush()
        self.proc = subprocess.Popen("exec " + cmd, shell=True, stdout=subprocess.PIPE, preexec_fn=os.setsid)

        # Don't wait for it in a thread; wait for it here.
        self.thread = None

        try:
            x = 0.30
            while True:                
                line = read(self.proc.stdout.fileno(), 1024)
                if line.strip() == "":
                    pass
                else:
                    line = self.__cleanOutput(line, video_id)
                    # print line # DEBUG
                    self.BusyDlg.SetProgress(self.DialogStatusPrefix + line, self.__calculateProgress(x))
                    self.BusyDlg.Fit()
                    self.BusyDlg.CenterOnParent()
                    self.Yielder.Yield()
                if not line: break
                if self.BusyDlg.Clicked:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                    break
                if x < 0.96:
                    x = x + (0.70 / 20.0)
            
            if self.BusyDlg.Clicked:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            else:
                self.procReturnCode = self.proc.wait()
        except OSError:
            self.procReturnCode = -1
        
        if self.BusyDlg.Clicked:
            self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Cancelled!", self.__calculateProgress(0.0))
            self.BusyDlg.Fit()
            self.BusyDlg.CenterOnParent()
            self.Yielder.Yield()
        else:
            self.BusyDlg.SetProgress(self.DialogStatusPrefix + "Done!", self.__calculateProgress(1.0))
            self.BusyDlg.Fit()
            self.BusyDlg.CenterOnParent()
            self.Yielder.Yield()

    # Do an HTTP request and return the DOM
    def get_dom_object(self, url_target):
        try:
            data = URL(url_target)
            dom_object = DOM(data.download(cached=False))
            return dom_object
        except:
            self.ErrorReason = 'Problem retrieving data for this url: ' + url_target + '.\nPlease check your Internet connection.'
            return None

    def getPopularVideo(self, searchKey):

        # start with forming the search
        searchKey = searchKey.rstrip().replace(' ', '+')
        fullSearchTerm = self.prefix_of_search_url + searchKey

        # Get the dom object from the search page
        search_result_page = self.get_dom_object(fullSearchTerm)

        # If No Search Results, there was an error
        if not search_result_page:
            return None

        # Get the search playlist
        search_result_dom_elements = []
        search_result_dom_elements.extend(search_result_page('div[class="yt-lockup-content"] h3[class="yt-lockup-title"] a'))

        video_link_title_dictionary = {}
        video_link_by_popularity = []
        for n in search_result_dom_elements:
            video_link = n.attributes['href']
            video_link_by_popularity.append('https://www.youtube.com' + video_link)

            video_title = n.attributes['title']
            video_link_title_dictionary[video_title] = 'https://www.youtube.com' + video_link

        # Return the first one in the list
        return video_link_by_popularity[0]

# Now instantiate a global ytDownloader object.
ytDownloader = pykYTDownloader()