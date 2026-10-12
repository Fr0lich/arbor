"""Qt (PySide6) UI package for Arbor.

Runs in parallel with the Tkinter UI in ``ui/`` (which is never modified).
Launch with ``python main_qt.py`` or ``python main.py --qt``.
"""
from ui_qt.add_objects import QtAddObjectsDialog
from ui_qt.base_queue import QtSpecimenQueueController
from ui_qt.bulk_edit import QtBulkEditDialog
from ui_qt.dashboard import QtDatabaseStatisticsDialog
from ui_qt.filter_dialog import QtFilterDialog
from ui_qt.gbif_dialog import QtGbifUpdateDialog
from ui_qt.gbif_review import QtGbifReviewDialog
from ui_qt.group_editor import QtGroupEditorDialog
from ui_qt.help_dialogs import QtKeyboardShortcutsDialog, QtUserGuideDialog
from ui_qt.historical_resolver import QtHistoricalResolverDialog
from ui_qt.ignored_words_dialog import QtIgnoredWordsDialog
from ui_qt.loading_dialog import QtLoadingDialog
from ui_qt.log_viewer import QtErrorLogDialog
from ui_qt.main_window import QtMainWindow
from ui_qt.new_database_wizard import QtNewDatabaseWizard
from ui_qt.problem_queue import QtProblemQueueDialog
from ui_qt.quick_peek import QtQuickPeekDialog
from ui_qt.recent_activity_dialog import QtRecentActivityDialog
from ui_qt.startup_dialog import QtStartupDialog
from ui_qt.unified_settings import QtUnifiedSettingsDialog

__all__ = [
    "QtAddObjectsDialog",
    "QtBulkEditDialog",
    "QtDatabaseStatisticsDialog",
    "QtErrorLogDialog",
    "QtFilterDialog",
    "QtGbifReviewDialog",
    "QtGbifUpdateDialog",
    "QtGroupEditorDialog",
    "QtHistoricalResolverDialog",
    "QtIgnoredWordsDialog",
    "QtKeyboardShortcutsDialog",
    "QtLoadingDialog",
    "QtMainWindow",
    "QtNewDatabaseWizard",
    "QtProblemQueueDialog",
    "QtQuickPeekDialog",
    "QtRecentActivityDialog",
    "QtSpecimenQueueController",
    "QtStartupDialog",
    "QtUnifiedSettingsDialog",
    "QtUserGuideDialog",
]
