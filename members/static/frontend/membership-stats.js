$( function () {
  var margin = {top: 10, right: 80, bottom: 45, left: 50},
      width = 960 - margin.left - margin.right,
      height = 500 - margin.top - margin.bottom,
      viewbox_width = width + margin.left + margin.right,
      viewbox_height = height + margin.top + margin.bottom;

  var parseDate = d3.timeFormat("%d-%b-%y").parse,
      bisectDate = d3.bisector(function(d) { return d.date; }).left;

  var x = d3.scaleTime()
      .range([0, width]);

  var y = d3.scaleLinear()
      .range([height, 0]);

  // see https://bl.ocks.org/d3noob/0e276dc70bb9184727ee47d6dd06e915
  var xAxis = d3.axisBottom(x)
      .tickSize(16)
      .tickFormat(d3.timeFormat("%b"));

  var yAxis = d3.axisLeft(y);

  // copied from matplotlib v2.0 - see https://matplotlib.org/users/dflt_style_changes.html#colors-in-default-property-cycle
  var colorcycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                '#9467bd', '#8c564b', '#e377c2', '#7f7f7f',
                '#bcbd22', '#17becf'];

  var line = d3.line()
      .x(function(d) { 
        return x(d.date); })
      .y(function(d) { 
        return y(d.count); });

  var entry_content = d3.select(".membership-stats")

  var svg = entry_content
    // for responsive solution see https://stackoverflow.com/questions/49034455/d3-chart-grows-but-wont-shrink-inside-a-flex-div#comment85075458_49034455
    // don't use width and height attributes!
    .append("svg")
      .attr("class", "chart")
      .attr("viewBox", "0 0 " + viewbox_width + " " + viewbox_height)
    .append("g")
      .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

  var formatDate = d3.timeFormat("%m/%d"); 
  var parseDate = d3.timeParse("%m-%d"),
      jan1 = parseDate("01-01"),
      dec31 = parseDate("12-31");
  x.domain([jan1, dec31]);

  let MAX_NUM_YEARS = 9;
  let data, 
      allyears=[];
  let numyearselect = '<select id="membership-numyear-select" name="numyear">\n';
  let numyearsoptions = [{val:'-1', text:'all'}]
  for (let i=MAX_NUM_YEARS; i>=1; i--) {
    numyearsoptions.push({val: i, text: i})
  }
  for (let i=0; i<numyearsoptions.length; i++) {
    numyear = numyearsoptions[i];
    numyearselect += '   <option value="' + numyear.val + '">' + numyear.text + '</option>\n';
  }
  numyearselect += '</select>';
  $( numyearselect ).appendTo('#membership-numyears');
  $( '#membership-numyear-select' ).select2({
                                      minimumResultsForSearch: Infinity,
                                      width: '75px',
                                  });
  $( '#membership-numyear-select' ).on('change', function(event) {
      membership_setshowlabels( $( '#membership-numyear-select' ).val() );
  });

  /**
   * show persistent elements based on numyears
   * 
   * @param {int} numyears - number of years, -1 means 'all'
   */
  function membership_setshowlabels( numyears ) {
    var alllabels = ['line', 'legend'];
    for (let labelndx=0; labelndx<alllabels.length; labelndx++) {
        let label = alllabels[labelndx];
        if (numyears == -1) {
            $( `.${label}-all` ).show();
        } else {
            $( `.${label}-all` ).hide();
            for (let yearndx=0; yearndx<numyears; yearndx++) {
                $( `.${label}-${allyears[yearndx]}` ).show();
            }    
        }
    }
  }

  /**
   * show or hide focus elements
   * 
   * @param {int} numyears - number of years, -1 means 'all'
   * @param {boolean} show - true if elements are to be shown, false to hide
   */
  function focus_showhide( numyears, show ) {
    if (show) {
        $( ".yeartable" ).show();
        let allfocuses = ['focus', 'tablerow'];
        for (let focusndx=0; focusndx<allfocuses.length; focusndx++) {
            let label = allfocuses[focusndx];
            if (numyears == -1) {
                $( `.${label}-all` ).show();
            } else {
                $( `.${label}-all` ).hide();
                for (let yearndx=0; yearndx<numyears; yearndx++) {
                    $( `.${label}-${allyears[yearndx]}` ).show();
                }   
            }
        }
    } else {
        $( ".yeartable" ).hide();
        $( ".focus-all" ).hide();
    }
  }

  var interest = get_group_val();
  d3.json('/' + interest + '/_memberstats')
    .then((contents) => {
      if (!contents.success) throw "error response from api";

      // data is page global for membership_setshowlabels()
      data = contents.data;
      var cachetime = contents.cachetime;

      // do this before parsing all the dates
      // NOTE: this code assumes contents.data[] is initially sorted by year
      var lastyearcounts = data[data.length-1]
          lastyear = lastyearcounts.year,
          lastcounts = lastyearcounts.counts;

      // now reverse sort data so most recent year shows up first in legend, table
      data.reverse();

      // data is [{year:year, counts: {['date':date, 'count':count}, ... ]}, ... ]
      // alldata is concatenation of all years' data for y.domain(d3.extent)
      alldata = [];
      for (let i=0; i<data.length; i++) {
        data[i].counts.forEach(function(d) {
          d.date = parseDate(d.date);
          // convert d.count to integer
          d.count = +d.count;
        });
        alldata = alldata.concat(data[i].counts);
      };

      // y.domain(d3.extent(alldata, function(d) { return d.count; }));
      y.domain([0, Math.ceil(d3.max(alldata, function(d) { return d.count})/100)*100]);

      svg.append("g")
          .attr("class", "x axis")
          .attr("transform", "translate(0," + height + ")")
          .call(xAxis)
        .selectAll(".tick text")
          .style("text-anchor", "start")
          .attr("x", 6)
          .attr("y", 6);

      svg.append("g")
          .attr("class", "y axis")
          .call(yAxis)
        .append("text")
          .attr("transform", "rotate(-90)")
          .attr("y", 6)
          .attr("dy", ".71em")
          .style("text-anchor", "end")
          .text("Num Members");

      colormap = [];
      for (let i=0; i<data.length; i++) {
        let year = data[i].year
        colormap.push({'year': year, 'color': colorcycle[i % colorcycle.length]});
        allyears.push(year);

        svg.append("path")
            .style("stroke", colormap[i].color)
            .datum(data[i].counts)
            .attr("class", "line line-all " + "line-" + year)
            .attr("d", line)
            .style("fill", "none")
            .style("stroke-width", "2px");

        var thisfocus = svg.append("g")
            .attr("class", "focus focus-all " + "focus-" + year)
            .attr("id","focus"+i)
            .style("display", "none");

        thisfocus.append("circle")
            .attr("r", 4.5)
            .style("fill", "none")
            .style("stroke", "steelblue");

        thisfocus.append("text")
            .style("text-anchor", "start")
            .attr("x", 4)
            .attr("y", 7)
            .attr("dy", ".35em");
      }

      var legend = svg.selectAll(".legend")
          .data(colormap)
        .enter().append("g")
          .attr("class", function(d, i) {return "legend legend-all "  + "legend-" + data[i].year})
          .attr("transform", function(d, i) { return "translate(" + i * 90 + ",0)"; });

      legend.append("rect")
          .attr("y", height + margin.bottom - 15)
          .attr("x", 60)
          .attr("width", 15)
          .attr("height", 15)
          .style("fill", function(d) { return d.color });

      legend.append("text")
          .attr("x", 15)
          .attr("y", height + margin.bottom - 15)
          .attr("dy", ".8em")
          .style("text-anchor", "bottom")
          .text(function(d) { return d.year; });

      // create table to show date / count
      // see http://bl.ocks.org/yan2014/c9dd6919658991d33b87
      var statscontainer = d3.selectAll(".membership-stats-table");
      var statstable = statscontainer.append("table")
        .attr("class", "focus yeartable")
        .style("display", "none");
      var statstablehdr = statstable.append("thead").append("tr");
      statstablehdr
        .selectAll("th")
        .data(["Date", "Count"])
        .enter()
        .append("th")
        .text(d => d)
      var statstablebody = statstable.append("tbody");
      var statstablerows = statstablebody
        .selectAll("tr")
        .data(data)
        .enter()
        .append("tr")
        .attr("class", d => `tablerow-all tablerow-${d.year}`);
      var statstablecells = statstablerows.selectAll("td")
        // start with first date of year
        .data((d) => [`${formatDate(d.counts[0].date)}/${d.year}`, d.counts[0].count])
        .enter()
        .append("td")
        .text(d => d)
        .attr("class", (d, i) => i == 0 ? "date" : "count TextCenter");
      
      // needs to be after paths are created, otherwise the mouse movement over the path looks like mouseout --
      // see https://developer.mozilla.org/en-US/docs/Web/CSS/pointer-events for proper way to do this (path style="pointer-events: none;")
      var mouseoverlay = svg.append("rect")
        .attr("class", "overlay")
        .attr("width", width + margin.right)
        .attr("height", height)
        .style("fill", "none")
        .style("pointer-events", "all");
  
      // margin overlay shows first values
      var marginoverlay = svg.append("rect")
        .attr("class", "overlay")
        .attr("width", margin.left)
        .attr("height", height)
        .attr("transform", "translate(" + -margin.left + ", 0)")
        .style("fill", "none")
        .style("pointer-events", "all");

        // handle mouse movement
      mouseoverlay
        .on("mouseover", function() { 
            focus_showhide( $( '#membership-numyear-select' ).val(), true );
         })
        .on("mouseout", function() { 
            focus_showhide( $( '#membership-numyear-select' ).val(), false );
         })
        .on("mousemove", mousemove);

      function mousemove(event) {
        var x0 = x.invert(d3.pointer(event)[0]);
        // console.log(`x0=${x0}`)
        for (i=0; i<data.length; i++) {
          var year = data[i].year;
          var j = bisectDate(data[i].counts, x0, 1);
          // use d0, d1 if in range
          if (j < data[i].counts.length) {
            var d0 = data[i].counts[j - 1],
                d1 = data[i].counts[j];
            var d = x0 - d0.date > d1.date - x0 ? d1 : d0;
          }
          else {
            var d = data[i].counts[data[i].counts.length-1]
          }
          // follows mouse
          var thisfocus = d3.select("#focus"+i);
          thisfocus.attr("transform", "translate(" + x(d.date) + "," + y(d.count) + ")");
          thisfocus.select("text").text(formatDate(d.date) + " " + d.count);
          // update table
          d3.select(`.tablerow-${year} .date`).text(`${formatDate(d.date)}/${year}`)
          d3.select(`.tablerow-${year} .count`).text(d.count)
        }
      }
      marginoverlay
        .on("mouseover", function() { 
            focus_showhide( $( '#membership-numyear-select' ).val(), true );
        })
        .on("mouseout", function() { 
            focus_showhide( $( '#membership-numyear-select' ).val(), false );
        })
        .on("mousemove", marginmove);
      function marginmove(event) {
        for (i=0; i<data.length; i++) {
          var year = data[i].year;
          // use d0, d1 if in range
          var d = data[i].counts[0];
          // follows mouse
          var thisfocus = d3.select("#focus"+i);
          thisfocus.attr("transform", "translate(" + x(d.date) + "," + y(d.count) + ")");
          thisfocus.select("text").text(formatDate(d.date) + " " + d.count);
          // update table
          d3.select(`.tablerow-${year} .date`).text(`${formatDate(d.date)}/${year}`)
          d3.select(`.tablerow-${year} .count`).text(d.count)
        }
      }
      })
    .catch((error) => {
      throw error;
    });
});

