import { AngleLeftIcon, AngleRightIcon } from "@patternfly/react-icons";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
} from "chart.js";
import { Button, Modal, ModalVariant } from "@patternfly/react-core";
import { setChartModal, setChartModalContent } from "actions/comparisonActions";
import { useDispatch, useSelector } from "react-redux";

import { Bar } from "react-chartjs-2";
import React from "react";

ChartJS.register(
  BarElement,
  Title,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale
);
const ChartModal = (props) => {
  const { isChartModalOpen, activeChart } = useSelector(
    (state) => state.comparison
  );

  const dispatch = useDispatch();
  const handleModalToggle = () => {
    dispatch(setChartModal(false));
  };
  const currIndex = props.dataToPlot.findIndex(
    (item) => item.data.id === activeChart.data.id
  );
  const prevId = props.dataToPlot[currIndex - 1]?.data?.id;
  const nextId = props.dataToPlot[currIndex + 1]?.data?.id;
  return (
    <Modal
      variant={ModalVariant.large}
      className="chart-expand-modal-container"
      isOpen={isChartModalOpen}
      aria-label="No header/footer modal"
      aria-describedby="modal-no-header-description"
      onClose={handleModalToggle}
    >
      {activeChart && (
        <div className="chart-modal-wrapper">
          <div className="modalBtn">
            <Button
              variant="plain"
              isDisabled={currIndex === 0}
              aria-label="Previous"
              onClick={() => dispatch(setChartModalContent(prevId))}
            >
              <AngleLeftIcon />
            </Button>
          </div>
          <div>
            <Bar
              options={activeChart.options}
              data={activeChart.data}
              width={750}
              height={450}
            />
          </div>
          <div className="modalBtn">
            <Button
              variant="plain"
              aria-label="Next"
              isDisabled={currIndex === props.dataToPlot.length - 1}
              onClick={() => dispatch(setChartModalContent(nextId))}
            >
              <AngleRightIcon />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default ChartModal;
