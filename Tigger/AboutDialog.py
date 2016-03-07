#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2002-2011
# The MeqTree Foundation &
# ASTRON (Netherlands Foundation for Research in Astronomy)
# P.O.Box 2, 7990 AA Dwingeloo, The Netherlands
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>,
# or write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from Tigger import release_string,svn_revision_html,pixmaps

import os.path
import time
import sys
import fnmatch
import traceback

from PyQt4.Qt import *



class AboutDialog (QDialog):
    def __init__(self,parent=None,name=None,modal=0,fl=None):
        if fl is None:
          fl = Qt.Dialog|Qt.WindowTitleHint;
        QDialog.__init__(self,parent,Qt.Dialog|Qt.WindowTitleHint);
        self.setModal(modal);

        image0 = pixmaps.tigger_logo.pm();

        # self.setSizeGripEnabled(0)
        LayoutWidget = QWidget(self)
        LayoutWidget.setSizePolicy(QSizePolicy.MinimumExpanding,QSizePolicy.MinimumExpanding);

        lo_top = QVBoxLayout(LayoutWidget)

        lo_title = QHBoxLayout(None)

        self.title_icon = QLabel(LayoutWidget)
        self.title_icon.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed);
        self.title_icon.setPixmap(image0)
        self.title_icon.setAlignment(Qt.AlignCenter)
        lo_title.addWidget(self.title_icon)

        self.title_label = QLabel(LayoutWidget)
        self.title_label.setWordWrap(True);
        lo_title.addWidget(self.title_label)
        lo_top.addLayout(lo_title)

        lo_logos = QHBoxLayout(None)
        lo_top.addLayout(lo_logos);
        for logo in ("astron",):
          icon = QLabel(LayoutWidget)
          icon.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed);
          icon.setPixmap(getattr(pixmaps,logo+"_logo").pm());
          icon.setAlignment(Qt.AlignCenter)
          lo_logos.addWidget(icon)

        lo_mainbtn = QHBoxLayout(None)
        lo_mainbtn.addItem(QSpacerItem(20,20,QSizePolicy.Expanding,QSizePolicy.Minimum))
        lo_top.addLayout(lo_mainbtn);

        self.btn_ok = QPushButton(LayoutWidget)
        self.btn_ok.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed);
        self.btn_ok.setMinimumSize(QSize(60,0))
        self.btn_ok.setAutoDefault(1)
        self.btn_ok.setDefault(1)
        lo_mainbtn.addWidget(self.btn_ok)
        lo_mainbtn.addItem(QSpacerItem(20,20,QSizePolicy.Expanding,QSizePolicy.Minimum))

        self.languageChange()

        LayoutWidget.adjustSize();

        #LayoutWidget.resize(QSize(489,330).expandedTo(LayoutWidget.minimumSizeHint()))
        #self.resize(QSize(489,330).expandedTo(self.minimumSizeHint()))
        # self.clearWState(Qt.WState_Polished)

        self.connect(self.btn_ok,SIGNAL("clicked()"),self.accept)

    def languageChange(self):
        self.setWindowTitle(self.__tr("About Tigger"))
        self.title_label.setText(self.__tr( \
          """<h3>Tigger %s</h3>
          <p>(C) 2010-2012 Oleg Smirnov & ASTRON<br>(Netherlands Institude for Radioastronomy)<br>
          Oude Hoogeveensedijk 4<br>
          7991 PD Dwingeloo, The Netherlands<br>
          http://www.astron.nl<br>
          <br>Please direct feedback and bug reports to osmirnov@gmail.com</p>
          """%(release_string) \
          ));

        self.btn_ok.setText(self.__tr("&OK"))

    def __tr(self,s,c = None):
        return qApp.translate("About",s,c)

