import "./index.less";

import * as APP_ROUTES from "utils/routeConstants";

import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from "chart.js";
import {
  Card,
  Divider,
  Flex,
  FlexItem,
  Gallery,
  GalleryItem,
} from "@patternfly/react-core";
import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";

import { Bar } from "react-chartjs-2";
import { getQuisbyData } from "actions/quisbyChartActions";
import { showToast } from "actions/toastActions";

ChartJS.register(
  BarElement,
  Title,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale
);

const QuisbyChartsComponent = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { datasetName, datasetId } = useParams();

  const { chartData, docLink } = useSelector((state) => state.quisbyChart);

  useEffect(() => {
    if (window.location.href.includes("results")) {
      if (!docLink) {
        dispatch(getQuisbyData([{ name: datasetName, rid: datasetId }]));
      }
    } else if (!docLink) {
      dispatch(
        showToast("danger", "Please select runs to compare from Overview page")
      );
      setTimeout(() => {
        navigate("/dashboard/" + APP_ROUTES.OVERVIEW);
      }, 1000);
    }
  }, [datasetId, datasetName, dispatch, docLink, navigate]);
  return (
    <div className="chart-container">
      <Flex className="heading-container">
        <FlexItem className="heading">Quisby Results</FlexItem>
        <FlexItem align={{ default: "alignRight" }}>
          {" "}
          <a href={docLink} rel="noreferrer" target="_blank">
            View in Google Sheet
          </a>
        </FlexItem>
      </Flex>
      <Divider component="div" className="header-separator" />
      {chartData && chartData.length > 0 && (
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
          {chartData.map((chart) => {
            return (
              <Card
                className="chart-card"
                isRounded
                isLarge
                key={chart.data.id}
              >
                <GalleryItem className="galleryItem chart-holder">
                  <Bar options={chart.options} data={chart.data} width={450} />
                </GalleryItem>
              </Card>
            );
          })}
        </Gallery>
      )}
    </div>
  );
};

export default QuisbyChartsComponent;
