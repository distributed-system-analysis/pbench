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
  EmptyState,
  EmptyStateBody,
  EmptyStateVariant,
  Gallery,
  GalleryItem,
} from "@patternfly/react-core";

import { Bar } from "react-chartjs-2";
import React from "react";
import { useSelector } from "react-redux";

ChartJS.register(
  BarElement,
  Title,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale
);
const EmptyStateExtraSmall = (props) => (
  <EmptyState variant={EmptyStateVariant.xs}>
    <div>{props.message}</div>
    <EmptyStateBody>Benchmark type is currently unsupported!</EmptyStateBody>
  </EmptyState>
);
const ChartGallery = () => {
  const { chartData, unsupportedType } = useSelector(
    (state) => state.comparison
  );
  return (
    <>
      {unsupportedType ? (
        <EmptyStateExtraSmall message={unsupportedType} />
      ) : (
        <>
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
              {chartData.map((chart) => (
                <Card
                  className="chart-card"
                  isRounded
                  isLarge
                  key={chart.data.id}
                >
                  <GalleryItem className="galleryItem chart-holder">
                    <Bar
                      options={chart.options}
                      data={chart.data}
                      width={450}
                    />
                  </GalleryItem>
                </Card>
              ))}
            </Gallery>
          )}
        </>
      )}
    </>
  );
};

export default ChartGallery;
