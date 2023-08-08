import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  SubTitle,
  Title,
  Tooltip,
} from "chart.js";
import { Card, Gallery, GalleryItem } from "@patternfly/react-core";
import { setChartModal, setChartModalContent } from "actions/comparisonActions";

import { Bar } from "react-chartjs-2";
import { ExpandArrowsAltIcon } from "@patternfly/react-icons";
import React from "react";
import { useDispatch } from "react-redux";

ChartJS.register(
  BarElement,
  Title,
  Tooltip,
  Legend,
  SubTitle,
  CategoryScale,
  LinearScale
);

const ChartGallery = (props) => {
  const dispatch = useDispatch();

  const handleExpandClick = (chartId) => {
    dispatch(setChartModal(true));
    dispatch(setChartModalContent(chartId));
  };
  return (
    <>
      {props.dataToPlot && props.dataToPlot.length > 0 && (
        <Gallery
          className="chart-wrapper"
          hasGutter
          minWidths={{
            default: "100%",
            md: "30rem",
            xl: "35rem",
          }}
          maxWidths={{
            md: "40rem",
            xl: "1fr",
          }}
        >
          {props.dataToPlot.map((chart) => (
            <Card className="chart-card" isRounded isLarge key={chart.data.id}>
              <div className="expand-icon-container">
                <div
                  className="icon-wrapper"
                  onClick={() => handleExpandClick(chart.data.id)}
                >
                  <ExpandArrowsAltIcon />
                </div>
              </div>
              <GalleryItem className="galleryItem chart-holder">
                <Bar options={chart.options} data={chart.data} width={450} />
              </GalleryItem>
            </Card>
          ))}
        </Gallery>
      )}
    </>
  );
};

export default ChartGallery;
