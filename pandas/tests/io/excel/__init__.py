import pytest

pytestmark = [
    pytest.mark.filterwarnings(
        # Looks like tree.getiterator is deprecated in favor of tree.iter
        "ignore:This method will be removed in future versions:"
        "PendingDeprecationWarning"
    ),
    pytest.mark.filterwarnings(
        "ignore:This method will be removed in future versions:DeprecationWarning"
    ),
    # GH 26552
    pytest.mark.filterwarnings(
        "ignore:As the xlwt package is no longer maintained:FutureWarning"
    ),
]
