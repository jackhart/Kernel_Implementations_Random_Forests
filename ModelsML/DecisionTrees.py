"""Implementations of Decision Trees"""

from .util import find_splits, gini
import numpy as np


class GeneralDecisionTree(object):
    """
    General Decision Tree implemented to support a CART algorithm

    Breiman, L., Friedman, J.H., Olshen, R., and Stone, C.J., 1984. Classification and Regression Tree
    ftp://ftp.boulder.ibm.com/software/analytics/spss/support/Stats/Docs/Statistics/Algorithms/14.0/TREE-CART.pdf
    """

    def __init__(self, name='root', children=None, split_rule=None, split_feature=None):
        self.name = name
        self.split_rule = split_rule  # e.g. lambda x: 0 if ... else 1 (returns indices of children)
        self.split_feature = split_feature

        self._children = []
        if children is not None:
            self.children = children

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self, children):
        assert len(children) == 2, "DecisionTree is a binary tree, must add two children at a time"

        for child in children:
            assert isinstance(child, GeneralDecisionTree), "Children must be DecisionTree objects"
            self._children.append(child)

    @children.deleter
    def children(self):
        for child in self._children:
            self._children.remove(child)

    def traverse(self, x):
        """Method for traversing tree given some example from data.  Recursive."""

        if self.children is None:
            return self
        try:
            child_index = self.split_rule(x[self.split_feature])
        except TypeError:
            return self  # edge case if test data contains NA

        child_index = np.asscalar(np.array(child_index))
        return self.children[child_index].traverse(x)

    def __repr__(self):
        return f"Tree(name='{self.name}', children={[child for child in self.children]})"

    def __str__(self):
        return self.__repr__()


class DecisionTreeClassification(GeneralDecisionTree):
    """
    Decision Tree implemented to support CART algorithm for Classification by saving only class counts

    Breiman, L., Friedman, J.H., Olshen, R., and Stone, C.J., 1984. Classification and Regression Tree
    ftp://ftp.boulder.ibm.com/software/analytics/spss/support/Stats/Docs/Statistics/Algorithms/14.0/TREE-CART.pdf
    """
    # TODO: Does not yet handle missing data exactly like algorithm described by Breiman

    def __init__(self, class_counts, n_subset, name='root',
                 children=None, split_rule=None, split_feature=None):
        """
        Initialize decision tree with functionality specific for traditional classification.

        :param class_counts, np.array, counts of examples for each class in node
        :param n_subset, int, number of examples represented by this node

        :param name, str, (default='root'), see parent class
        :param children, list, (default=None), see parent class
        :param split_rule, lambda function, (default=None), function that returns index of child for split
        :param split_feature, int, (default=None), index of feature to split on in dataset for current node
        """

        super().__init__(name=name, children=children,
                         split_rule=split_rule, split_feature=split_feature)

        self.class_counts = class_counts
        self.n_subset = n_subset

    def grow_tree(self, X, y, data_types, best_gini, classes,
                  min_size=2, max_depth=None, current_depth=0, max_gini=1):
        """
        Grows tree for given dataset for a classification task.  Recursive.

        :param X, np.array, subset of variables to split on
        :param y, np.array, subset of classes
        :param data_types, list, data types (i.e. numeric, ordinal, or categorical) of X
        :param best_gini, double, gini of the current node being split
        :param classes, np.array, array of all possible class values

        :param min_size, int, (default=2) minimum allowable number of examples making up a node
        :param max_depth, int, (default=None) maximum number of branches off nodes allowed
        :param current_depth, used in recursion to keep track of tree depth
        :param max_gini, int, (default=1) maximum gini you allow for a split to happen
        """

        if (y.size < min_size) or (best_gini == 0.0):
            # stopping criterion: node be smaller than min size
            # if node is pure, don't split
            return
        if max_depth is not None:
            if current_depth > max_depth:
                # stopping criterion: cannot build tree greater than max size
                return

        best_thr, best_p_ind, best_type = None, None, None

        for idx, data_type in zip(range(X.shape[1]), data_types):
            x = X[:, idx]

            new_thr, new_gini, left_distribution, right_distribution = self._best_split_classification(x, y, data_type, classes)

            if new_gini < best_gini:  # minimize gini
                best_gini, best_thr, best_p_ind, best_type = new_gini, new_thr, idx, data_type

        # if better split found
        if (best_thr is not None) and (max_gini > best_gini):

            # set current tree values for split
            self.split_feature = best_p_ind
            if best_type in ['n', 'o']:
                self.split_rule = lambda x_val: (x_val > best_thr).astype(int)
            else:
                self.split_rule = lambda x_val: (x_val == best_thr).astype(int)

            # calculate class distributions for children
            splits = self.split_rule(X[:, best_p_ind])

            # subset data for splits
            right_y, right_x = y[splits == 1],  X[splits == 1, :]
            left_y, left_x = y[splits == 0], X[splits == 0, :]

            if (right_y.size < min_size) or (left_y.size < min_size):
                # stopping criterion: if either child is less than min size, don't split
                self.split_rule = None
                self.split_feature = None
                return

            # grow left child
            left_tree = DecisionTreeClassification(name=f"{self.name}_{best_p_ind}_child1",
                                                   class_counts=np.array(left_distribution),
                                                   n_subset=np.sum(left_distribution))

            left_tree.grow_tree(left_x, left_y, data_types, gini(np.array(left_distribution), left_y.size),
                                classes=classes, min_size=min_size, max_depth=max_depth, current_depth=current_depth + 1)

            # grow right child
            right_tree = DecisionTreeClassification(name=f"{self.name}_{best_p_ind}_child2",
                                                    class_counts=np.array(right_distribution),
                                                    n_subset=np.sum(right_distribution))

            right_tree.grow_tree(right_x, right_y, data_types, gini(np.array(right_distribution), right_y.size),
                                 classes=classes, min_size=min_size, max_depth=max_depth, current_depth=current_depth + 1)

            # add children to tree
            self.children = [left_tree, right_tree]

        else:
            # stopping criterion: gini not improved
            # gini is greater than user-specified maximum gini
            # gini is greater than user-specified maximum gini
            return

    def prune(self):
        # TODO: Implement pruning method
        # Unclear on how the CART algorithm post-prunes compared to C4.5
        raise NotImplementedError

    @staticmethod
    def _best_split_classification(feature_values, labels, data_type, classes):
        """
         Determines the best split possible for a given feature.
         Helper method for grow_tree()

         :param feature_values, np.array, subset of variables for given feature to split on
         :param labels, np.array, subset of classes
         :param data_type, str, data type (i.e. numeric, ordinal, or categorical) for given feature
         :param classes, np.array, array of all possible class values

         :returns tuple, (best_thr, impurity, best_left_dist, best_right_dist)
                  Returns best value to split on and associated impurity,
                  along with the class distributions in each node.
         """

        best_thr, impurity, best_left_dist, best_right_dist = None, 1, None, None   # current min impurity
        possible_thresholds = np.unique(feature_values)

        num_labels = labels.size

        if data_type == 'c':
            possible_thresholds = find_splits(possible_thresholds)

        for threshold in possible_thresholds:

            if data_type == 'c':
                selection = np.isin(feature_values, threshold)
            else:
                selection = feature_values > threshold

            right = labels[selection]
            left = labels[~selection]

            num_right = right.size

            # compute distribution of labels for each split
            unique_right, right_distribution = np.unique(right, return_counts=True)
            unique_left, left_distribution = np.unique(left, return_counts=True)

            # assure class distributions are in the correct order and the correct shape
            new_right, new_left = np.zeros(classes.shape), np.zeros(classes.shape)
            inx_right = np.isin(classes, unique_right, assume_unique=True)
            inx_left = np.isin(classes, unique_left, assume_unique=True)
            new_right[inx_right], new_left[inx_left] = right_distribution, left_distribution

            right_distribution, left_distribution = new_right, new_left

            # compute impurity of split based on the distribution
            gini_right = gini(np.array(right_distribution), num_right)
            gini_left = gini(np.array(left_distribution), num_labels - num_right)

            # compute weighted total impurity of the split
            gini_split = (num_right * gini_right + (num_labels - num_right) * gini_left) / num_labels

            if gini_split < impurity:
                best_thr, impurity, best_left_dist, best_right_dist = threshold, gini_split, left_distribution, right_distribution

        # returns the threshold with the min associated impurity value --> best split threshold
        return best_thr, impurity, best_left_dist, best_right_dist

    def __repr__(self):
        return f"DecisionTreeClassification(name='{self.name}', children={[child for child in self.children]})"

    def __str__(self):
        return self.__repr__()


class KeDTClassification(DecisionTreeClassification):
    """
     Decision Tree implemented to support Kernel Decision Trees.  These trees will support KERF models discussed here:

        Olson, Matthew and Abraham J. Wyner. “Making Sense of Random Forest Probabilities: a Kernel Perspective”.
        ArXiv https://arxiv.org/abs/1812.05792

        Scornet, E. “Random Forests and Kernel Methods”.
        ArXiv https://arxiv.org/abs/1502.03836

    This decision tree follows the same algorithm as DecisionTreeClassification; however, the classification method
    is tweaked to support theoretical kernel interpretations of probabilities.
    """

    def __init__(self, name='root',
                 children=None, split_rule=None, split_feature=None):
        """
        Initialize decision tree with functionality specific for traditional classification.

        :param name, str, (default='root'), see parent class
        :param children, list, (default=None), see parent class
        :param split_rule, lambda function, (default=None), function that returns index of child for split
        :param split_feature, int, (default=None), index of feature to split on in dataset for current node
        """
        super(GeneralDecisionTree).__init__(name=name, children=children,
                                            split_rule=split_rule, split_feature=split_feature)
        # TODO: Implement init

    # overload grow tree method
    def grow_tree(self, X, y, data_types, best_gini, classes,
                  min_size=2, max_depth=None, current_depth=0, max_gini=1):
        """
        Grows tree for given dataset for a classification task.  Recursive.

        :param X, np.array, subset of variables to split on
        :param y, np.array, subset of classes
        :param data_types, list, data types (i.e. numeric, ordinal, or categorical) of X
        :param best_gini, double, gini of the current node being split
        :param classes, np.array, array of all possible class values

        :param min_size, int, (default=2) minimum allowable number of examples making up a node
        :param max_depth, int, (default=None) maximum number of branches off nodes allowed
        :param current_depth, used in recursion to keep track of tree depth
        :param max_gini, int, (default=1) maximum gini you allow for a split to happen
        """
        # TODO: Implement grow_tree
        raise NotImplementedError

    def __repr__(self):
        return f"KeRFClassification(name='{self.name}', children={[child for child in self.children]})"

    def __str__(self):
        return self.__repr__()
