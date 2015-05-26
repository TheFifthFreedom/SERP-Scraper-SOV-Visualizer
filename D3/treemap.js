// Treemap
var margin = {top: 20, right: 0, bottom: 0, left: 0},
    width = 960,
    height = 500 - margin.top - margin.bottom,
    formatNumber = d3.format(",d"),
    transitioning;

var x = d3.scale.linear()
    .domain([0, width])
    .range([0, width]);

var y = d3.scale.linear()
    .domain([0, height])
    .range([0, height]);

var treemap = d3.layout.treemap()
    .children(function(d, depth) { return depth ? null : d._children; })
    .sort(function(a, b) { return a.value - b.value; })
    .ratio(height / width * 0.5 * (1 + Math.sqrt(5)))
    .round(false);

var svg = d3.select("#treemap").append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.bottom + margin.top)
    .attr("class", "treemap")
    .style("margin-left", -margin.left + "px")
    .style("margin-right", -margin.right + "px")
  .append("g")
    .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
    .style("shape-rendering", "crispEdges");

var grandparent = svg.append("g")
    .attr("class", "grandparent");

grandparent.append("rect")
    .attr("y", -margin.top)
    .attr("width", width)
    .attr("height", margin.top);

grandparent.append("text")
    .attr("x", 6)
    .attr("y", 6 - margin.top)
    .attr("dy", ".75em");

var curlyBracketSvg = d3.select("#treemap").append("svg")
    .attr("width", width)
    .attr("height", height + margin.bottom + margin.top)
    .attr("class", "curlyBracket")
    .style("margin-left", -margin.left + "px")
    .style("margin-right", -margin.right + "px");

var curlyBracketData = [ {"x": 1, "y": 1},
    {"x": 1, "y": 10},
    {"x": width / 2 - 10, "y": 10},
    {"x": width / 2, "y": 20},
    {"x": width / 2 + 10, "y": 10},
    {"x": width - 1, "y": 10},
    {"x": width - 1, "y": 1}
];

var curlyBracketFunction = d3.svg.line()
    .x(function(d) {return d.x;})
    .y(function(d) {return d.y;})
    .interpolate("linear");

var curlyBracket = curlyBracketSvg.append("path")
    .attr("d", curlyBracketFunction(curlyBracketData))
    .attr("stroke", "orange")
    .attr("stroke-width", 2)
    .attr("fill", "none");

curlyBracketSvg.append("text")
    .attr("x", 0)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Volume:");

curlyBracketSvg.append("text")
    .attr("x", width/6)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Maps:");

curlyBracketSvg.append("text")
    .attr("x", 2*width/6)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Image results:");

curlyBracketSvg.append("text")
    .attr("x", 3*width/6)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Image Blocks:");

curlyBracketSvg.append("text")
    .attr("x", 4*width/6)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Answer Boxes:");

curlyBracketSvg.append("text")
    .attr("x", 5*width/6)
    .attr("y", 50)
    .attr("font-size", "15px")
    .text("Knowledge Graphs:");

var curlyBracketVolumeText = curlyBracketSvg.append("text")
    .attr("x", 0)
    .attr("y", 70)
    .attr("font-size", "15px");

var curlyBracketMapsText = curlyBracketSvg.append("text")
    .attr("x", width/6)
    .attr("y", 70)
    .attr("font-size", "15px");

var curlyBracketImagesText = curlyBracketSvg.append("text")
    .attr("x", 2*width/6)
    .attr("y", 70)
    .attr("font-size", "15px");

var curlyBracketImageBlocksText = curlyBracketSvg.append("text")
    .attr("x", 3*width/6)
    .attr("y", 70)
    .attr("font-size", "15px");

var curlyBracketAnswerBoxesText = curlyBracketSvg.append("text")
    .attr("x", 4*width/6)
    .attr("y", 70)
    .attr("font-size", "15px");

var curlyBracketKnowledgeGraphText = curlyBracketSvg.append("text")
    .attr("x", 5*width/6)
    .attr("y", 70)
    .attr("font-size", "15px");

// Indented Tree
var indentedTreeMargin = {top: 10, right: 20, bottom: 30, left: 20},
    indentedTreeWidth = 300 - indentedTreeMargin.left - indentedTreeMargin.right,
    barHeight = 13,
    barWidth = indentedTreeWidth * .8;

var i = 0,
    duration = 400,
    indentedTreeRoot;

var indentedTree = d3.layout.tree()
    .nodeSize([0, 20]);

var diagonal = d3.svg.diagonal()
    .projection(function(d) { return [d.y, d.x]; });

var indentedTreeSvg = d3.select("#indentedTree").append("svg")
    .attr("width", indentedTreeWidth + indentedTreeMargin.left + indentedTreeMargin.right)
  .append("g")
    .attr("transform", "translate(" + indentedTreeMargin.left + "," + indentedTreeMargin.top + ")");

var indentedTreeFilter = false;

// Outlier-detection
var searchVolumes = [], // List of all search volumes for interquartile range
    sumSearchVolumes = 0, // Sum of all search volumes for standard deviation
    sumSearchVolumesSquared = 0, // Sum of all search volumes squared for standard deviation
    length = 0, // Search volume count
    thresholds,
    lowerThreshold,
    upperThreshold;


d3.json("semantic_map.json", function(root) {

    // Indentend Tree
    update(indentedTreeRoot = clean(root), indentedTreeFilter);
    click(indentedTreeRoot);

    var indentedTreeNodes = indentedTree.nodes(indentedTreeRoot);
    var indentedTreeCurrentNodeId = indentedTreeRoot.node_id;

    // First, there's a few things we need to do to the JSON
    // before it's ready to be visualized
    // Because of the nature of the D3 Treemap implementation,
    // the value you want the cells' area to represent has to
    // have its variable named 'value' for each node
    // Plus, we have to add dummy nodes at every depth since
    // the sum of all search volumes of a node's children isn't
    // equal to the node's search volume
    // That's why we must first sanitize the tree, which will
    // take care of all of that
    // It will also gather all the search volume values for
    // outlier detection which we'll get to in a second
    var sanRoot = returnSanitized(root);

    // We now have what we need to compute the standard deviation
    // and the interquartile range - both of which will help us find
    // outliers. Both methods are valid - here we're using the standard
    // deviation one, but we left the interquartile code for future use
    thresholds = getStandardDeviationThresholds(sumSearchVolumes, sumSearchVolumesSquared, length);
    // var thresholds = getInterquartileRangeThresholds(searchVolumes);
    lowerThreshold = thresholds[0];
    upperThreshold = thresholds[1];

    initialize(sanRoot);
    accumulate(sanRoot);
    layout(sanRoot, false);
    display(sanRoot, false);

    function initialize(root) {
      root.x = root.y = 0;
      root.dx = width;
      root.dy = height;
      root.depth = 0;
    }

    // Aggregate the values for internal nodes. This is normally done by the
    // treemap layout, but not here because of our custom implementation.
    // We also take a snapshot of the original children (_children) to avoid
    // the children being overwritten when layout is computed.
    function accumulate(d) {
      return (d._children = d.children)
          ? d.value = d.children.reduce(function(p, v) { return p + accumulate(v); }, 0)
          : d.value;
    }

    // Compute the treemap layout recursively such that each group of siblings
    // uses the same size (1×1) rather than the dimensions of the parent cell.
    // This optimizes the layout for the current zoom state. Note that a wrapper
    // object is created for the parent node for each group of siblings so that
    // the parent’s dimensions are not discarded as we recurse. Since each group
    // of sibling was laid out in 1×1, we must rescale to fit using absolute
    // coordinates. This lets us use a viewport to zoom.
    function layout(d, filter) {
      if (d._children) {
        saneChildren = d._children.filter(function(d){
            if (d.name == 'dummy'){
              return false;
            }
            else if (filter && (d.value < lowerThreshold || d.value > upperThreshold)){
              return false;
            }
            return true;
        });
        treemap.nodes({_children: saneChildren});
        d._children.forEach(function(c) {
          c.x = d.x + c.x * d.dx;
          c.y = d.y + c.y * d.dy;
          c.dx *= d.dx;
          c.dy *= d.dy;
          c.parent = d;
          layout(c, filter);
        });
      }
    }

    function display(d, filter) {
      // Total serch volume for current view
      var totalSearchVolume = 0;
      var totalMaps = 0;
      var totalImages = 0;
      var totalImageBlocks = 0;
      var totalAnswerBoxes = 0;
      var totalKnowledgeGraphs = 0;
      // Include/Exclude outliers
      d3.select("select").on("change", function() {
          if (this.value == 'no_outliers'){
              layout(d, true);
              $('g.depth > g').remove();
              display(d, true);
              indentedTreeFilter = true;
              update(indentedTreeRoot, indentedTreeFilter);
          }
          else {
              layout(d, false);
              $('g.depth > g').remove();
              display(d, false);
              indentedTreeFilter = false;
              update(indentedTreeRoot, indentedTreeFilter);
          }
      });
      saneChildren = d._children.filter(function(d){
          if (d.name == 'dummy'){
            return false;
          }
          else if (filter && (d.value < lowerThreshold || d.value > upperThreshold)){
            return false;
          }
          totalMaps += d.map_result;
          totalImages += d.image_results;
          totalImageBlocks += d.image_mega_block;
          totalAnswerBoxes += d.answer_box;
          totalKnowledgeGraphs += d.knowledge_graph;
          totalSearchVolume += d.value;
          return true;
      });

      grandparent
          .datum(d.parent)
          .on("click", transition)
        .select("text")
          .text(name(d));

      var g1 = svg.insert("g", ".grandparent")
          .datum(d)
          .attr("class", "depth");

      var g = g1.selectAll("g")
          .data(saneChildren)
        .enter().append("g");

      g.filter(function(d) { return d._children; })
          .classed("children", true)
          .on("click", transition);

      g.selectAll(".child")
          .data(function(d) {
              if (d._children){
                return d._children.filter(function(d){
                    if (d.name == 'dummy'){
                      return false;
                    }
                    else if (filter && (d.value < lowerThreshold || d.value > upperThreshold)){
                      return false;
                    }
                    return true;
                });
              }
              else{
                return [d];
              }
              return d._children || [d];
          })
        .enter().append("rect")
          .attr("class", "child")
          .call(rect);

      g.append("rect")
          .attr("class", "parent")
          .call(rect)
        .append("title")
          .text(function(d) { return formatNumber(d.value); });

      g.append("text")
          .attr("dy", ".75em")
          .text(function(d) { return d.name; })
          .call(text);

      curlyBracketVolumeText.text(totalSearchVolume);
      curlyBracketMapsText.text(totalMaps);
      curlyBracketImagesText.text(totalImages);
      curlyBracketImageBlocksText.text(totalImageBlocks);
      curlyBracketAnswerBoxesText.text(totalAnswerBoxes);
      curlyBracketKnowledgeGraphText.text(totalKnowledgeGraphs);

      function transition(d) {
        // Indented Tree Transition
        treeMapCurrentNodeId = d.node_id;
        if (indentedTreeCurrentNodeId < treeMapCurrentNodeId){
            var indentedTreeTargetNode = indentedTreeNodes.filter(function(d){
                if (d.node_id == treeMapCurrentNodeId){return true;}
                else {return false;}
            })[0];
            click(indentedTreeTargetNode);
        }
        else{
          var indentedTreeTargetNode = indentedTreeNodes.filter(function(d){
              if (d.node_id == indentedTreeCurrentNodeId){return true;}
              else {return false;}
          })[0];
          click(indentedTreeTargetNode);
        }
        indentedTreeCurrentNodeId = treeMapCurrentNodeId;

        // Treemap Transition
        if (transitioning || !d) return;
        transitioning = true;

        var g2 = display(d, filter),
            t1 = g1.transition().duration(750),
            t2 = g2.transition().duration(750);

        // Update the domain only after entering new elements.
        x.domain([d.x, d.x + d.dx]);
        y.domain([d.y, d.y + d.dy]);

        // Enable anti-aliasing during the transition.
        svg.style("shape-rendering", null);

        // Draw child nodes on top of parent nodes.
        svg.selectAll(".depth").sort(function(a, b) { return a.depth - b.depth; });

        // Fade-in entering text.
        g2.selectAll("text").style("fill-opacity", 0);

        // Transition to the new view.
        t1.selectAll("text").call(text).style("fill-opacity", 0);
        t2.selectAll("text").call(text).style("fill-opacity", 1);
        t1.selectAll("rect").call(rect);
        t2.selectAll("rect").call(rect);

        // Remove the old node when the transition is finished.
        t1.remove().each("end", function() {
          svg.style("shape-rendering", "crispEdges");
          transitioning = false;
        });
      }

      return g;
    }

    function text(text) {
      text.attr("x", function(d) { return x(d.x) + 6; })
          .attr("y", function(d) { return y(d.y) + 6; });
    }

    function rect(rect) {
      rect.attr("x", function(d) { return x(d.x); })
          .attr("y", function(d) { return y(d.y); })
          .attr("width", function(d) { return x(d.x + d.dx) - x(d.x); })
          .attr("height", function(d) { return y(d.y + d.dy) - y(d.y); });
    }

    function name(d) {
      return d.parent
          ? name(d.parent) + " > " + d.name
          : d.name;
    }

    function returnSanitized(node) {
        var sanNode = {};
        sanNode.node_id = node.node_id;
        sanNode.name = node.name;
        sanNode.type = node.type;
        sanNode.duplicate = node.duplicate;
        sanNode.value = node.average_monthly_search_volume;
        sanNode.competition = node.competition;
        sanNode.map_result = node.map_result;
        sanNode.image_results = node.image_results;
        sanNode.image_mega_block = node.image_mega_block;
        sanNode.answer_box = node.answer_box;
        sanNode.knowledge_graph = node.knowledge_graph;

        sumSearchVolumes += node.average_monthly_search_volume;
        sumSearchVolumesSquared += (node.average_monthly_search_volume * node.average_monthly_search_volume);
        searchVolumes.push(node.average_monthly_search_volume);
        length += 1;

        if (node.children) {
            sanNode.children = [];
            var childrenSumSearchVolume = 0
            node.children.forEach(function (child, index, array) {
                childrenSumSearchVolume += child.average_monthly_search_volume;
                sanNode.children.push(returnSanitized(child));
            });
            var searchVolumeDiff = node.average_monthly_search_volume - childrenSumSearchVolume;
            sanNode.children.push({"value": searchVolumeDiff, "name": "dummy"});
        }
        return sanNode;
    }

    function getStandardDeviationThresholds(sum, sumSquared, length){ // Using the standard deviation
      var mean = sum / length;
      var varience = (sumSquared / length) - (mean * mean);
      var sd = Math.sqrt(varience);
      var lowerThreshold = mean - (3*sd);
      var upperThreshold = mean + (3*sd);
      return [lowerThreshold, upperThreshold];
    }

    function getInterquartileRangeThresholds(array){ // Using quartiles and the interquartal range
      // First we sort the numbers
      array.sort(function(a,b){return a-b});
      // Then we find the first quartile
      var q1 = findMedian(array.slice(0, Math.floor(array.length / 2)));
      // Then we find the third quartile
      var q3 = findMedian(array.slice(Math.ceil(array.length / 2)));
      // Then we find the interquartal range
      var iqr = q3 - q1;
      // Which leads us to the thresholds
      var lowerThreshold = q1 - (1.5*iqr); // iqr multiple can be tweaked
      var upperThreshold = q3 + (1.5*iqr); // iqr multiple can be tweaked
      return [lowerThreshold, upperThreshold];
    }

    function findMedian(array){ // Finds the median of an array
      var half = Math.floor(array.length/2);

      if(array.length % 2)
          // There are an odd number of elements in the array; the median
          // is the middle one
          return array[half];
      else
          // There are an even number of elements in the array; the median
          // is the average of the middle two
          return (array[half-1] + array[half]) / 2.0;
    }
});

function update(source, filter) {

  // Compute the flattened node list. TODO use d3.layout.hierarchy.
  var nodes;
  if (filter){
      nodes = indentedTree.nodes(indentedTreeRoot).filter(function(d){
          if (d['average_monthly_search_volume'] < lowerThreshold || d['average_monthly_search_volume'] > upperThreshold){return false;}
          else {return true;}
      });
  }
  else{
      nodes = indentedTree.nodes(indentedTreeRoot);
  }

  var height = Math.max(500, nodes.length * barHeight + indentedTreeMargin.top + indentedTreeMargin.bottom);

  d3.select("#indentedTree > svg").transition()
      .duration(duration)
      .attr("height", height);

  d3.select(self.frameElement).transition()
      .duration(duration)
      .style("height", height + "px");

  // Compute the "layout".
  nodes.forEach(function(n, i) {
    n.x = i * barHeight;
  });

  // Update the nodes…
  var node = indentedTreeSvg.selectAll("g.node")
      .data(nodes, function(d) { return d.id || (d.id = ++i); });

  var nodeEnter = node.enter().append("g")
      .attr("class", "node")
      .attr("transform", function(d) { return "translate(" + source.y0 + "," + source.x0 + ")"; })
      .style("opacity", 1e-6);

  // Enter any new nodes at the parent's previous position.
  nodeEnter.append("rect")
      .attr("y", -barHeight / 2)
      .attr("height", barHeight)
      .attr("width", barWidth)
      .style("fill", color);
      // .on("click", click);

  nodeEnter.append("text")
      .attr("dy", 3.5)
      .attr("dx", 5.5)
      .text(function(d) { return d.name; });

  // Transition nodes to their new position.
  nodeEnter.transition()
      .duration(duration)
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })
      .style("opacity", 1);

  node.transition()
      .duration(duration)
      .attr("transform", function(d) { return "translate(" + d.y + "," + d.x + ")"; })
      .style("opacity", 1)
    .select("rect")
      .style("fill", color);

  // Transition exiting nodes to the parent's new position.
  node.exit().transition()
      .duration(duration)
      .attr("transform", function(d) { return "translate(" + source.y + "," + source.x + ")"; })
      .style("opacity", 1e-6)
      .remove();

  // Update the links…
  var link = indentedTreeSvg.selectAll("path.link")
      .data(indentedTree.links(nodes), function(d) { return d.target.id; });

  // Enter any new links at the parent's previous position.
  link.enter().insert("path", "g")
      .attr("class", "link")
      .attr("d", function(d) {
        var o = {x: source.x0, y: source.y0};
        return diagonal({source: o, target: o});
      })
    .transition()
      .duration(duration)
      .attr("d", diagonal);

  // Transition links to their new position.
  link.transition()
      .duration(duration)
      .attr("d", diagonal);

  // Transition exiting nodes to the parent's new position.
  link.exit().transition()
      .duration(duration)
      .attr("d", function(d) {
        var o = {x: source.x, y: source.y};
        return diagonal({source: o, target: o});
      })
      .remove();

  // Stash the old positions for transition.
  nodes.forEach(function(d) {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}

// Toggle children on click.
function click(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else {
    d.children = d._children;
    d._children = null;
  }
  update(d, indentedTreeFilter);
}

function color(d) {
  return d.children ? "orange" : "#ccc";
}

function clean(node){
    var sanNode = {};
    sanNode.node_id = node.node_id;
    sanNode.name = node.name;
    sanNode['average_monthly_search_volume'] = node['average_monthly_search_volume'];
    sanNode._children = [];
    if(node.children){
        node.children.forEach(function(child, index, array){
            sanNode._children.push(clean(child));
        });
    }
    else{
        delete sanNode._children;
    }
    return sanNode;
}
