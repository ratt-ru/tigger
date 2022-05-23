# Copyright (C) 2002-2022
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

"""Checks that Tigger-LSM, PyQt5 and PyQt-Qwt are available for Tigger to operate."""
missing = []  # list of missing dependencies


def close_btn(btn):
    """QMessageBox close button handler to close GUI and print error message to terminal."""
    msg_box.close()
    sys.exit(error_msg)


try:
    try:
        from Tigger.Models import ModelClasses  # check Tigger-LSM is available
    except ImportError:
        missing.append("Tigger-LSM")
        pass

    try:
        from PyQt5.Qt import Qt  # check PyQt5 is available
    except ImportError:
        missing.append("PyQt5")
        pass

    try:
        from PyQt5.QtOpenGL import QGLWidget  # check PyQt5 Qt OpenGL is available
    except ImportError:
        missing.append("PyQt5.QtOpenGL")
        pass

    try:
        from PyQt5.QtSvg import QSvgWidget  # check PyQt5 Qt SVG is available
    except ImportError:
        missing.append("PyQt5.QtSvg")
        pass

    try:
        from PyQt5.Qwt import QwtPlotZoomer  # check PyQt-Qwt is available

        test_qwt = callable(
            getattr(QwtPlotZoomer, 'setZoomStack', False))  # check correct version of PyQt-Qwt is installed
    except ImportError:
        missing.append("PyQt5.Qwt")
        test_qwt = False
        pass

except ImportError:
    deps_available = False
    pass
else:
    if test_qwt:
        deps_available = True
    else:
        deps_available = False
        missing.append("PyQt-Qwt>=2.0.0")

if not deps_available:
    import sys

    error_msg = f"Error: Dependencies have not been met {missing}, please check your installation. \n" \
                "See https://github.com/ratt-ru/tigger for further information."

    # load GUI error message if possible
    if 'PyQt5' not in missing:
        from PyQt5.Qt import QMessageBox, QApplication, QPalette, QColor

        # set dark theme palatte
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Light, QColor(68, 68, 68))
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.black)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218, 192))
        palette.setColor(QPalette.HighlightedText, Qt.white)

        # create default QApp and set dark theme palette
        app = QApplication(sys.argv)
        app.setPalette(palette)

        # create GUI dialog window to display error message
        msg_box = QMessageBox()
        msg_box.setWindowFlag(Qt.CustomizeWindowHint, True)
        msg_box.setWindowFlag(Qt.WindowCloseButtonHint, False)
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Tigger")
        msg_box.setText(f"<b>Error</b><br/><br/>Dependencies have not been met: <br/><br/>{missing}<br/><br/>"
                        f"Please check your installation. "
                        f"<br/><br/>See <a href='https://github.com/ratt-ru/tigger'>https://github.com/ratt-ru/tigger</a>"
                        f" for further information.")
        msg_box.setStandardButtons(QMessageBox.Close)
        msg_box.buttonClicked.connect(close_btn)
        msg_box.exec_()
    else:
        sys.exit(error_msg)
