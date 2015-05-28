// Get JSON data
treeJSON = d3.json("semantic_map.json", function(error, treeData) {

    // Calculate total nodes, max label length
    var totalNodes = 0;
    var maxLabelLength = 0;
    // variables for drag/drop
    var selectedNode = null;
    var draggingNode = null;
    // panning variables
    var panSpeed = 200;
    var panBoundary = 20; // Within 20px from edges will pan when dragging.
    // Misc. variables
    var i = 0;
    var duration = 750;
    var root;

    // size of the diagram
    var viewerWidth = $(document).width();
    var viewerHeight = $(document).height();

    var tree = d3.layout.tree()
        .size([viewerHeight, viewerWidth]);

    // define a d3 diagonal projection for use by the node paths later on.
    var diagonal = d3.svg.diagonal()
        .projection(function(d) {
            return [d.y, d.x];
        });

    // Scale for node color based on competiton
    var competitionScaleColors = ['#f6faaa','#FEE08B','#FDAE61','#F46D43','#D53E4F','#9E0142'];
    var competitionScale = d3.scale.quantile()
        .domain([0, 1])
        .range(competitionScaleColors);

    // Scale for node size based on search volume
    var volumeScale = d3.scale.linear()
        .domain([0, 500000])
        .range([3, 10])
        .clamp(true);

    // A recursive helper function for performing some setup by walking through all nodes
    function visit(parent, visitFn, childrenFn) {
        if (!parent) return;

        visitFn(parent);

        var children = childrenFn(parent);
        if (children) {
            var count = children.length;
            for (var i = 0; i < count; i++) {
                visit(children[i], visitFn, childrenFn);
            }
        }
    }

    // Call visit function to establish maxLabelLength
    visit(treeData, function(d) {
        totalNodes++;
        maxLabelLength = Math.max(d.name.length, maxLabelLength);

    }, function(d) {
        return d.children && d.children.length > 0 ? d.children : null;
    });


    // sort the tree according to the node names

    function sortTree() {
        tree.sort(function(a, b) {
            return b.name.toLowerCase() < a.name.toLowerCase() ? 1 : -1;
        });
    }
    // Sort the tree initially incase the JSON isn't in a sorted order.
    // sortTree();

    // TODO: Pan function, can be better implemented.

    function pan(domNode, direction) {
        var speed = panSpeed;
        if (panTimer) {
            clearTimeout(panTimer);
            translateCoords = d3.transform(svgGroup.attr("transform"));
            if (direction == 'left' || direction == 'right') {
                translateX = direction == 'left' ? translateCoords.translate[0] + speed : translateCoords.translate[0] - speed;
                translateY = translateCoords.translate[1];
            } else if (direction == 'up' || direction == 'down') {
                translateX = translateCoords.translate[0];
                translateY = direction == 'up' ? translateCoords.translate[1] + speed : translateCoords.translate[1] - speed;
            }
            scaleX = translateCoords.scale[0];
            scaleY = translateCoords.scale[1];
            scale = zoomListener.scale();
            svgGroup.transition().attr("transform", "translate(" + translateX + "," + translateY + ")scale(" + scale + ")");
            d3.select(domNode).select('g.node').attr("transform", "translate(" + translateX + "," + translateY + ")");
            zoomListener.scale(zoomListener.scale());
            zoomListener.translate([translateX, translateY]);
            panTimer = setTimeout(function() {
                pan(domNode, speed, direction);
            }, 50);
        }
    }

    // Define the zoom function for the zoomable tree

    function zoom() {
        svgGroup.attr("transform", "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")");
    }


    // define the zoomListener which calls the zoom function on the "zoom" event constrained within the scaleExtents
    var zoomListener = d3.behavior.zoom().scaleExtent([0.1, 3]).on("zoom", zoom);

    function initiateDrag(d, domNode) {
        draggingNode = d;
        d3.select(domNode).select('.ghostCircle').attr('pointer-events', 'none');
        d3.selectAll('.ghostCircle').attr('class', 'ghostCircle show');
        d3.select(domNode).attr('class', 'node activeDrag');

        svgGroup.selectAll("g.node").sort(function(a, b) { // select the parent and sort the path's
            if (a.id != draggingNode.id) return 1; // a is not the hovered element, send "a" to the back
            else return -1; // a is the hovered element, bring "a" to the front
        });
        // if nodes has children, remove the links and nodes
        if (nodes.length > 1) {
            // remove link paths
            links = tree.links(nodes);
            nodePaths = svgGroup.selectAll("path.link")
                .data(links, function(d) {
                    return d.target.id;
                }).remove();
            // remove child nodes
            nodesExit = svgGroup.selectAll("g.node")
                .data(nodes, function(d) {
                    return d.id;
                }).filter(function(d, i) {
                    if (d.id == draggingNode.id) {
                        return false;
                    }
                    return true;
                }).remove();
        }

        // remove parent link
        parentLink = tree.links(tree.nodes(draggingNode.parent));
        svgGroup.selectAll('path.link').filter(function(d, i) {
            if (d.target.id == draggingNode.id) {
                return true;
            }
            return false;
        }).remove();

        dragStarted = null;
    }

    // define the baseSvg, attaching a class for styling and the zoomListener
    var baseSvg = d3.select("#tree-container").append("svg")
        .attr("width", viewerWidth)
        .attr("height", viewerHeight)
        .attr("class", "overlay")
        .call(zoomListener).on("dblclick.zoom", null);


    // Define the drag listeners for drag/drop behaviour of nodes.
    dragListener = d3.behavior.drag()
        .on("dragstart", function(d) {
            if (d == root) {
                return;
            }
            dragStarted = true;
            nodes = tree.nodes(d);
            d3.event.sourceEvent.stopPropagation();
            // it's important that we suppress the mouseover event on the node being dragged. Otherwise it will absorb the mouseover event and the underlying node will not detect it d3.select(this).attr('pointer-events', 'none');
        })
        .on("drag", function(d) {
            if (d == root) {
                return;
            }
            if (dragStarted) {
                domNode = this;
                initiateDrag(d, domNode);
            }

            // get coords of mouseEvent relative to svg container to allow for panning
            relCoords = d3.mouse($('svg').get(0));
            if (relCoords[0] < panBoundary) {
                panTimer = true;
                pan(this, 'left');
            } else if (relCoords[0] > ($('svg').width() - panBoundary)) {

                panTimer = true;
                pan(this, 'right');
            } else if (relCoords[1] < panBoundary) {
                panTimer = true;
                pan(this, 'up');
            } else if (relCoords[1] > ($('svg').height() - panBoundary)) {
                panTimer = true;
                pan(this, 'down');
            } else {
                try {
                    clearTimeout(panTimer);
                } catch (e) {

                }
            }

            d.x0 += d3.event.dy;
            d.y0 += d3.event.dx;
            var node = d3.select(this);
            node.attr("transform", "translate(" + d.y0 + "," + d.x0 + ")");
            updateTempConnector();
        }).on("dragend", function(d) {
            if (d == root) {
                return;
            }
            domNode = this;
            if (selectedNode) {

                // Checking if we're moving a child to its current parent
                var alreadyChild = false;
                for (var child in selectedNode.children) {
                    if (selectedNode.children[child].id == draggingNode.id){
                      alreadyChild = true;
                    }
                }

                // the original nature of the link is now irrelevant
                if (alreadyChild == false) {  draggingNode.type = 'broken'; }

                // now remove the element from the parent, and insert it into the new elements children
                var index = draggingNode.parent.children.indexOf(draggingNode);
                if (index > -1) {
                    draggingNode.parent.children.splice(index, 1);
                }
                if (typeof selectedNode.children !== 'undefined' || typeof selectedNode._children !== 'undefined') {
                    if (typeof selectedNode.children !== 'undefined') {
                        selectedNode.children.push(draggingNode);
                    } else {
                        selectedNode._children.push(draggingNode);
                    }
                } else {
                    selectedNode.children = [];
                    selectedNode.children.push(draggingNode);
                }

                // Make sure that the node being added to is expanded so user can see added node is correctly moved
                expand(selectedNode);
                // sortTree();
                endDrag();
            } else {
                endDrag();
            }
        });

    function endDrag() {
        selectedNode = null;
        d3.selectAll('.ghostCircle').attr('class', 'ghostCircle');
        d3.select(domNode).attr('class', 'node');
        // now restore the mouseover event or we won't be able to drag a 2nd time
        d3.select(domNode).select('.ghostCircle').attr('pointer-events', '');
        updateTempConnector();
        if (draggingNode !== null) {
            update(root);
            centerNode(draggingNode);
            draggingNode = null;
        }
    }

    // Helper functions for collapsing and expanding nodes.
    function collapse(d) {
        if (d.children) {
            d._children = d.children;
            d._children.forEach(collapse);
            d.children = null;
        }
    }

    function expand(d) {
        if (d._children) {
            d.children = d._children;
            d.children.forEach(expand);
            d._children = null;
        }
    }

    var overCircle = function(d) {
        selectedNode = d;
        updateTempConnector();
    };
    var outCircle = function(d) {
        selectedNode = null;
        updateTempConnector();
    };

    // Function to update the temporary connector indicating dragging affiliation
    var updateTempConnector = function() {
        var data = [];
        if (draggingNode !== null && selectedNode !== null) {
            // have to flip the source coordinates since we did this for the existing connectors on the original tree
            data = [{
                source: {
                    x: selectedNode.y0,
                    y: selectedNode.x0
                },
                target: {
                    x: draggingNode.y0,
                    y: draggingNode.x0
                }
            }];
        }
        var link = svgGroup.selectAll(".templink").data(data);

        link.enter().append("path")
            .attr("class", "templink")
            .attr("d", d3.svg.diagonal())
            .attr('pointer-events', 'none');

        link.attr("d", d3.svg.diagonal());

        link.exit().remove();
    };

    // Function to center node when clicked/dropped so node doesn't get lost when collapsing/moving with large amount of children.

    function centerNode(source) {
        scale = zoomListener.scale();
        x = -source.y0;
        y = -source.x0;
        x = x * scale + viewerWidth / 2;
        y = y * scale + viewerHeight / 2;
        d3.select('g').transition()
            .duration(duration)
            .attr("transform", "translate(" + x + "," + y + ")scale(" + scale + ")");
        zoomListener.scale(scale);
        zoomListener.translate([x, y]);
    }

    // Toggle children function

    function toggleChildren(d) {
        if (d.children) {
            d._children = d.children;
            d.children = null;
        } else if (d._children) {
            d.children = d._children;
            d._children = null;
        }
        return d;
    }

    // Toggle children on click.

    function click(d) {
        if (d3.event.defaultPrevented) return; // click suppressed
        d = toggleChildren(d);
        update(d);
        centerNode(d);
    }

    function update(source) {
        // Compute the new height, function counts total children of root node and sets tree height accordingly.
        // This prevents the layout looking squashed when new nodes are made visible or looking sparse when nodes are removed
        // This makes the layout more consistent.
        var levelWidth = [1];
        var childCount = function(level, n) {

            if (n.children && n.children.length > 0) {
                if (levelWidth.length <= level + 1) levelWidth.push(0);

                levelWidth[level + 1] += n.children.length;
                n.children.forEach(function(d) {
                    childCount(level + 1, d);
                });
            }
        };
        childCount(0, root);
        var newHeight = d3.max(levelWidth) * 25; // 25 pixels per line
        tree = tree.size([newHeight, viewerWidth]);

        // Compute the new tree layout.
        var nodes = tree.nodes(root).reverse(),
            links = tree.links(nodes);

        // Set widths between levels based on maxLabelLength.
        nodes.forEach(function(d) {
            d.y = (d.depth * (maxLabelLength * 10)); //maxLabelLength * 10px
            // alternatively to keep a fixed scale one can set a fixed depth per level
            // Normalize for fixed-depth by commenting out below line
            // d.y = (d.depth * 500); //500px per level.
        });

        // Update the nodesâ€¦
        node = svgGroup.selectAll("g.node")
            .data(nodes, function(d) {
                return d.id || (d.id = ++i);
            });

        // Enter any new nodes at the parent's previous position.
        var nodeEnter = node.enter().append("g")
            .call(dragListener)
            .attr("class", function(d) { if (baseSvg.select("#check").node().checked && d.duplicate == true) {return "node hidden";} else {return "node";} })
            .attr("transform", function(d) {
                return "translate(" + source.y0 + "," + source.x0 + ")";
            })
            .on('click', click);

        nodeEnter.append("circle")
            .attr('class', 'nodeCircle')
            .attr("r", 0)
            .style("fill", function(d) {
                return d._children ? "lightsteelblue" : "#fff";
            });

        nodeEnter.append("text")
            .attr("x", function(d) {
                return d.children || d._children ? -10 : 10;
            })
            .attr("dy", ".35em")
            .attr('class', 'nodeText')
            .attr("text-anchor", function(d) {
                return d.children || d._children ? "end" : "start";
            })
            .text(function(d) {
                return d.name;
            })
            .style("fill-opacity", 0);

        // phantom node to give us mouseover in a radius around it
        nodeEnter.append("circle")
            .attr('class', 'ghostCircle')
            .attr("r", 30)
            .attr("opacity", 0.2) // change this to zero to hide the target area
        .style("fill", "red")
            .attr('pointer-events', 'mouseover')
            .on("mouseover", function(node) {
                overCircle(node);
            })
            .on("mouseout", function(node) {
                outCircle(node);
            });

        // Update the text to reflect whether node has children or not.
        node.select('text')
            .attr("x", function(d) {
                return d.children || d._children ? -10 : 10;
            })
            .attr("text-anchor", function(d) {
                return d.children || d._children ? "end" : "start";
            })
            .text(function(d) {
                return d.name;
            });

        // Change the circle fill depending on whether it has children and is collapsed
        node.select("circle.nodeCircle")
            .attr("r", function(d) { return volumeScale(d.average_monthly_search_volume) })
            .style("fill", function(d) { return competitionScale(d.competition); })
            .style("stroke", function(d) { return d._children ? "steelblue" : competitionScale(d.competition);})
            .style("stroke-width", function(d) { return d._children ? 1.5 : 0;});
            // .style("fill", function(d) {
            //     return d._children ? "lightsteelblue" : "#fff";
            // });

        // Transition nodes to their new position.
        var nodeUpdate = node.transition()
            .duration(duration)
            .attr("transform", function(d) {
                return "translate(" + d.y + "," + d.x + ")";
            });

        // Fade the text in
        nodeUpdate.select("text")
            .style("fill-opacity", 1);

        // Transition exiting nodes to the parent's new position.
        var nodeExit = node.exit().transition()
            .duration(duration)
            .attr("transform", function(d) {
                return "translate(" + source.y + "," + source.x + ")";
            })
            .remove();

        nodeExit.select("circle")
            .attr("r", 0);

        nodeExit.select("text")
            .style("fill-opacity", 0);

        // Update the linksâ€¦
        var link = svgGroup.selectAll("path.link")
            .data(links, function(d) {
                return d.target.id;
            });

        // Enter any new links at the parent's previous position.
        link.enter().insert("path", "g")
            .attr('class', function(d) { if (baseSvg.select("#check").node().checked && d.target.duplicate == true && d.target.hasOwnProperty('children') == false && d.target.hasOwnProperty('_children') == false) {return "link " + d.target.type + ' hidden';} else {return "link " + d.target.type} })
            //.attr("class", function(d) { return "link " + d.target.type })
            .attr("d", function(d) {
                var o = {
                    x: source.x0,
                    y: source.y0
                };
                return diagonal({
                    source: o,
                    target: o
                });
            });

        // Transition links to their new position.
        link.transition()
            .duration(duration)
            .attr("d", diagonal);

        // Transition exiting nodes to the parent's new position.
        link.exit().transition()
            .duration(duration)
            .attr("d", function(d) {
                var o = {
                    x: source.x,
                    y: source.y
                };
                return diagonal({
                    source: o,
                    target: o
                });
            })
            .remove();

        // Stash the old positions for transition.
        nodes.forEach(function(d) {
            d.x0 = d.x;
            d.y0 = d.y;
        });

        // sanitizedNodes = returnSanitized(root);
        // console.log(sanitizedNodes);
        // console.log(JSON.stringify(sanitizedNodes));
    }

    function returnSanitized(node) {
        var sanNode = {};
        sanNode.node_id = node.node_id;
        sanNode.name = node.name;
        sanNode.type = node.type;
        sanNode.duplicate = node.duplicate;
        sanNode.average_monthly_search_volume = node.average_monthly_search_volume;
        sanNode.competition = node.competition;
        sanNode.image_results = node.image_results;
        sanNode.image_mega_block = node.image_mega_block;
        sanNode.map_result = node.map_result;
        sanNode.answer_box = node.answer_box;
        sanNode.knowledge_graph = node.knowledge_graph;
        sanNode.children = [];
        if (node.children) {
            node.children.forEach(function (child, index, array) {
                sanNode.children.push(returnSanitized(child));
            });
        }
        return sanNode;
    }

    // Append a group which holds all nodes and which the zoom Listener can act upon.
    var svgGroup = baseSvg.append("g");

    // Include the legend in the top left corner
    var legend = baseSvg.append("g");
    legend.selectAll('rect')
        .data(competitionScaleColors)
        .enter()
        .append('rect')
        .attr('width', 17)
        .attr('height', 17)
        .attr('x',function(d,i){
            return 102 + i*18;
        })
        .attr('fill',function(d){
            return d;
        });

    legend.selectAll('circle')
        .data([3, 6.5, 10])
        .enter()
        .append('circle')
        .style('fill', 'none')
        .style('stroke', 'steelblue')
        .attr('r', function(d) { return d })
        .attr('cx', function(d, i) { return 124 + i * 30})
        .attr('cy', 40);

    legend.selectAll('text')
        .data(['Competition', 'Search Volume', 'Related Searches', 'Autocomplete Results', 'K.G. Suggestions', 'Disambiguation Results', 'Autocorrect (Forced)', 'Autocorrect (Suggested)', 'Broken', 'No Duplicates'])
        .enter()
        .append('text')
        .text(function(d) { return d; })
        .style('font', '14px sans-serif')
        .attr('y', function(d, i) {
            if (i == 0) { return 14; }
            else if (i == 1) { return 44; }
            else if (i == 9) { return 240; }
            else { return 44 + i * 20; }
         });

    legend.selectAll('line')
        .data(['#86D9DA', '#CADF70', '#F1A5B3', '#E1B96C', '#8BE0A4', '#C8BEE5', 'red'])
        .enter()
        .append('line')
        .style('stroke', function(d) { return d })
        .style('stroke-width', '15px')
        .attr('x1', 170)
        .attr('x2', 210)
        .attr('y1', function(d, i) { return 80 + i * 20 })
        .attr('y2', function(d, i) { return 80 + i * 20 });

    legend.append('foreignObject')
        .attr("width", 100)
        .attr("height", 100)
        .attr('x', 85)
        .attr('y', 225)
        .append("xhtml:body")
        .html("<form><input type=checkbox id=check /></form>")
        .on("click", function(){
            var nodes = svgGroup.selectAll('g.node');
            var links = svgGroup.selectAll('path.link');
            // Hide duplicates accordingly
            if (baseSvg.select("#check").node().checked) {
                nodes.filter(function(d) {
                    if (d.duplicate == true && d.hasOwnProperty('children') == false && d.hasOwnProperty('_children') == false) {return true;}
                    else {return false;}
                }).attr('class', function(){return this.getAttribute('class') + ' hidden';});

                nodes.filter(function(d) {
                    if (d.duplicate == true && (d.hasOwnProperty('_children') == true || d.hasOwnProperty('children') == true)) {return true;}
                    else {return false;}
                }).select('text').attr('class', function(){return this.getAttribute('class') + ' hidden';});

                links.filter(function(d) {
                    if (d.target.duplicate == true && d.target.hasOwnProperty('children') == false && d.target.hasOwnProperty('_children') == false) {return true;}
                    else {return false;}
                }).attr('class', function(){return this.getAttribute('class') + ' hidden';});

                // Hide bar chart
                $('.duplicatesMiniChart').hide();
            }
            else {
                nodes.filter(function(d) {
                    if (d.duplicate == true && d.hasOwnProperty('children') == false && d.hasOwnProperty('_children') == false) {return true;}
                    else {return false;}
                }).attr('class', function(){return this.getAttribute('class').replace(' hidden', '');});

                nodes.filter(function(d) {
                    if (d.duplicate == true && (d.hasOwnProperty('_children') == true || d.hasOwnProperty('children') == true)) {return true;}
                    else {return false;}
                }).select('text').attr('class', function(){return this.getAttribute('class').replace(' hidden', '');});

                links.filter(function(d) {
                    if (d.target.duplicate == true && d.target.hasOwnProperty('children') == false && d.target.hasOwnProperty('_children') == false) {return true;}
                    else {return false;}
                }).attr('class', function(){return this.getAttribute('class').replace(' hidden', '');});

                // Show bar chart
                $('.duplicatesMiniChart').show();
            }
        });

    // Include the bar chart in the bottom left corner
    var margin = {top: 30, right: 30, bottom: 50, left: 30},
        width = 200 - margin.left,
        height = 250 - margin.bottom;

    var xScale = d3.scale.ordinal()
        .rangeRoundBands([0, width], .1);

    var yScale = d3.scale.linear()
        .range([height, 0]);

    var xAxis = d3.svg.axis()
        .scale(xScale)
        .orient("bottom");

    var yAxis = d3.svg.axis()
        .scale(yScale)
        .orient("left")
        .ticks(10);

    var barChart = baseSvg.append("g")
        .attr("class", "duplicatesMiniChart")
        .attr("transform", "translate(" + margin.left + "," + (viewerHeight - 250) + ")");

    // Clickable overlay
    baseSvg.append('rect')
        .attr('class', 'duplicatesMiniChart')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', 'none')
        .attr('pointer-events', 'all')
        .attr("transform", "translate(" + margin.left + "," + (viewerHeight - 250) + ")")
        .attr('cursor', 'pointer')
        .on("click", function(){
            $('#popup').popup('show');
        })

    d3.csv("duplicates.csv", function(error, data) {
      // Transposing the duplicates data: we want to map the keyword count per frequency
      duplicates = []
      data.forEach(function(object){
          var frequency = object['Frequency'];
          if (frequency > 1){
            var result = duplicates.filter(function(duplicate) {
                return duplicate.Frequency == frequency;
            });
            if (result.length == 0){
                duplicates.push({'Frequency': frequency, 'Number of Keywords': 1});
            }
            else{
                result[0]['Number of Keywords'] += 1;
            }
          }
      });

      xScale.domain(duplicates.map(function(d) { return d.Frequency; }));
      yScale.domain([0, d3.max(duplicates, function(d) { return d['Number of Keywords']; })]);

      barChart.append("g")
          .attr("class", "x axis")
          .attr("transform", "translate(0," + height + ")")
          .call(xAxis)
        .append('text')
          .attr('x', width/2)
          .attr("y", 20)
          .attr("dy", ".71em")
          .style("text-anchor", "middle")
          .text("Frequency");

      barChart.append("g")
          .attr("class", "y axis")
          .call(yAxis)
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("dy", ".71em")
          .style("text-anchor", "end")
          .text("Number of Keywords");

      barChart.selectAll(".bar")
          .data(duplicates)
        .enter().append("rect")
          .attr("class", "bar")
          .attr("x", function(d) { return xScale(d.Frequency); })
          .attr("width", xScale.rangeBand())
          .attr("y", function(d) { return yScale(d['Number of Keywords']); })
          .attr("height", function(d) { return height - yScale(d['Number of Keywords']); });

    });

    // Define the root
    root = treeData;
    root.x0 = viewerHeight / 2;
    root.y0 = 0;

    // Layout the tree initially and center on the root node.
    update(root);
    centerNode(root);
});

function populatePopup(){
    d3.csv("duplicates.csv", function(error, data) {
      var margin = {top: 20, right: 20, bottom: 200, left: 40},
          width = 960 - margin.left - margin.right,
          height = 700 - margin.top - margin.bottom;

      var x = d3.scale.ordinal()
          .rangeRoundBands([0, width], .1, 0.5);

      var y = d3.scale.linear()
          .range([height, 0]);

      var xAxis = d3.svg.axis()
          .scale(x)
          .orient("bottom");

      var yAxis = d3.svg.axis()
          .scale(y)
          .orient("left")
          .ticks(10);

      var svg = d3.select("#popup").append("svg")
          .attr("width", width + margin.left + margin.right)
          .attr("height", height + margin.top + margin.bottom)
        .append("g")
          .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

      // We're only concerned about the keywords with a frequency higher than 2
      duplicates = []
      data.forEach(function(object){
          var keyword = object['Keyword'];
          var frequency = object['Frequency'];
          if (frequency > 1){
            duplicates.push({'Keyword': keyword, 'Frequency': frequency});
          }
      });

      x.domain(duplicates.map(function(d) { return d.Keyword; }));
      y.domain([0, d3.max(duplicates, function(d) { return d.Frequency; })]);

      svg.append("g")
          .attr("class", "x axis")
          .attr("transform", "translate(0," + height + ")")
          .call(xAxis)
          .selectAll('text')
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", "-.15em")
            .attr("transform", "rotate(-65)");

      svg.append("g")
          .attr("class", "y axis")
          .call(yAxis)
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("dy", ".71em")
          .style("text-anchor", "end")
          .text("Frequency");

      svg.selectAll(".bar")
          .data(duplicates)
        .enter().append("rect")
          .attr("class", "bar")
          .attr("x", function(d) { return x(d.Keyword); })
          .attr("width", x.rangeBand())
          .attr("y", function(d) { return y(d.Frequency); })
          .attr("height", function(d) { return height - y(d.Frequency); });

    });
};

$(document).ready(function(){
    $('#popup').popup({
      scrolllock: true,
      transition: 'all 0.3s',
      setzindex: true,
      beforeopen: function() { populatePopup(); },
      closetransitionend: function(){ $('#popup').empty() }
    });
})
